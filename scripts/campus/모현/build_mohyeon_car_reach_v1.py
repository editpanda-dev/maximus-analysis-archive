"""모현(글캠) 차(택시·자가용) 30분 도달: 카카오모빌리티 길찾기로 상권 군집·명소 대표점까지 잰다.

    대상   = SBIZ 20km 안 점포 DBSCAN 군집(30점포 이상) 대표점 + 명소 원천(카카오·도시공원·공공시설개방·TourAPI·공공체육, minor 제외)
             직선 18km 밖은 부르지 않음(국도 평균 40km/h로도 30분 밖)
    시간   = 카카오모빌리티 directions summary duration(호출 시점 교통 반영, 출발 시각 지정 없음), 택시요금 함께 저장
    가게   = 각 점포는 가장 가까운 측정점(1.5km 안)의 차 시간 + 남은 직선거리 ÷ 시속 20km 로 근사
응답은 데이터/캐시/모현_kakao_car/에 캐시. 카카오 응답이라 재배포 금지.
실행: zsh -ic '~/.venvs/maximus/bin/python -I 분석/모현/build_mohyeon_car_reach_v1.py'
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_mohyeon_attractions_v0 as at  # noqa: E402
import build_mohyeon_scorecard_v0 as sc  # noqa: E402

CACHE = sc.ROOT / "데이터/캐시/모현_kakao_car"
MAX_CALL_KM = 18


def drive(lat: float, lon: float) -> dict:
    p = CACHE / f"{lat:.5f}_{lon:.5f}.json"
    if p.exists():
        return json.loads(p.read_text())
    q = urllib.parse.urlencode({"origin": f"{sc.CAMPUS[1]},{sc.CAMPUS[0]}", "destination": f"{lon},{lat}",
                                "priority": "TIME", "summary": "true"})
    req = urllib.request.Request(f"https://apis-navi.kakaomobility.com/v1/directions?{q}",
                                 headers={"Authorization": f"KakaoAK {os.environ['KAKAO_REST_API_KEY']}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    p.write_text(json.dumps(data, ensure_ascii=False))
    time.sleep(0.1)
    return data


def summary(data: dict) -> tuple[float, float, float]:
    r = (data.get("routes") or [{}])[0]
    if r.get("result_code") != 0:
        return np.nan, np.nan, np.nan
    s = r["summary"]
    return s["duration"] / 60, s["distance"] / 1000, s.get("fare", {}).get("taxi", np.nan)


def probes() -> pd.DataFrame:
    raw = pd.read_csv(sc.RAW / "sbiz_stores_within20km_globalcampus_202606.csv", dtype=str)
    raw[["경도", "위도"]] = raw[["경도", "위도"]].astype(float)
    g = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw["경도"], raw["위도"]), crs=4326).to_crs(5179)
    c, _ = sc.build_clusters(g)
    clusters = pd.DataFrame({"probe": "상권", "name": c.sigungu + " " + c.dong + " " + c.landmark.fillna(""),
                             "category": c.stores.astype(str) + "점포", "lat": c.dest_lat, "lon": c.dest_lon, "stores": c.stores})
    p = at.load_places()
    minor = (p.category.isin(at.MINOR_CATEGORIES) & ~p.address_name.str.contains(r"\d", na=False)) | p.category.isin(at.SMALL_PARKS)
    p = p[~minor]
    places = pd.DataFrame({"probe": "명소", "name": p.place_name, "category": p.category, "type": p.type,
                           "source": p.source, "address": p.address_name, "lat": p.y, "lon": p.x})
    out = pd.concat([clusters, places], ignore_index=True)
    out["straight_km"] = sc.haversine_km(out.lat, out.lon).round(2)
    return out[out.straight_km <= MAX_CALL_KM].reset_index(drop=True)


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    pr = probes()
    print("probes", len(pr), pr.probe.value_counts().to_dict())
    res = [summary(drive(r.lat, r.lon)) for r in pr.itertuples()]
    pr[["car_min", "car_km", "taxi_won"]] = pd.DataFrame(res, index=pr.index)
    pr["car_min"] = pr.car_min.round(1)
    pr.to_csv(sc.OUT / "mohyeon_car_reach_v1.csv", index=False, encoding="utf-8-sig")
    ok = pr[pr.car_min <= 30]
    print("car<=30", len(ok), ok.probe.value_counts().to_dict(), "stores in clusters", int(ok.stores.sum()))


if __name__ == "__main__":
    main()
