"""서울캠퍼스 30분 추천 v1: 동대문 786 상권 스코어카드를 서울캠 한 곳 출발로 다시 거른다.

    출발   = 한국외대 서울캠퍼스(카카오 좌표 37.59754, 127.05785)
    도달   = ODsay searchPubTransPathT 최단 totalTime(대기 미포함), 상권 폴리곤 대표점까지. 직선 12km 밖은 부르지 않음.
             응답은 데이터/캐시/서울캠_odsay에 캐시(한도·IP 오류는 캐시 안 함)
    점수   = food_shopping_v1(식사·쇼핑·하위분류·카페 잠정)과 발견 태그(목적형·청년형·저녁형·주말형·특화)를 그대로 붙임
    숨은 가게 태그 = build_seoulcampus_area_tags_v1 (노포·10년+·오래된 카페·착한가격 개수)
    경계   = ODsay 시간 25~30분은 배차 대기를 넣으면 30분을 넘을 수 있어 wait_risk로 표시(글캠: 대기 넣으면 30분 군집 11→6)
    한도   = ODsay 429면 더 부르지 않고 캐시된 것만으로 출력. 실제 한도가 하루 약 30건이라(10-30, 10-31 모두 30건 뒤 429)
             불확실한 직선 4~8km 상권부터 부른다. 아직 못 부른 곳은 reach_status로 추정 표시
             (캐시 89건: 8~10km 12곳 모두 38분 이상, 4~6km 중앙값 26분, 6~8km 중앙값 33.5분)
               추정 안 = 직선 4km 이하, 추정 밖 = 직선 8km 초과, 미측정 = 4~8km
    출력   = 데이터/가공/서울캠/seoulcampus_areas_reach_v1.csv (30분 안 전체) + 목적별 상위
실행: zsh -ic '~/.venvs/maximus/bin/python -I 분석/서울캠/build_seoulcampus_recommendations_v1.py'  (IP별 ODsay 키는 ODSAY_IP_KEYS, 없으면 ODSAY_API_KEY)
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())
REPO = ROOT / "maximus-analysis-archive/data/processed"
CACHE = ROOT / "데이터/캐시/서울캠_odsay"
OUT = ROOT / "데이터/가공/서울캠"
CAMPUS = (37.59754, 127.05785)
MAX_STRAIGHT_KM = 12
REACH_MIN = 30
TOP_N = 10
WAIT_RISK_MIN = 25
SENS_MIN = [25, 30, 35]
EST_IN_KM, EST_OUT_KM = 4, 8


# ODsay 서버 키는 IP에 묶인다. ODSAY_IP_KEYS="<IP>=<키 환경변수 이름>,..." 로 IP별 키를 고르고, 맞는 IP가 없으면 ODSAY_API_KEY
def odsay_key() -> str:
    with urllib.request.urlopen("https://api.ipify.org", timeout=10) as r:
        ip = r.read().decode().strip()
    by_ip = dict(x.split("=", 1) for x in os.environ.get("ODSAY_IP_KEYS", "").split(",") if "=" in x)
    name = by_ip.get(ip, "ODSAY_API_KEY")
    if not os.environ.get(name):
        raise RuntimeError(f"현재 IP에 맞는 ODsay 키({name})가 환경변수에 없음 (ODsay 콘솔에 IP 등록 후 추가)")
    return os.environ[name]


ODSAY_KEY = None
QUOTA_HIT = False


def odsay(lat: float, lon: float) -> dict:
    p = CACHE / f"{lat:.5f}_{lon:.5f}.json"
    if p.exists():
        return json.loads(p.read_text())
    global ODSAY_KEY, QUOTA_HIT
    if QUOTA_HIT:
        return {"uncalled": True}
    ODSAY_KEY = ODSAY_KEY or odsay_key()
    q = urllib.parse.urlencode({"SX": CAMPUS[1], "SY": CAMPUS[0], "EX": lon, "EY": lat, "apiKey": ODSAY_KEY})
    with urllib.request.urlopen(f"https://api.odsay.com/v1/api/searchPubTransPathT?{q}", timeout=30) as r:
        data = json.loads(r.read())
    err = data.get("error")
    code = str((err[0] if isinstance(err, list) else err or {}).get("code", ""))
    if code == "429":  # 일일 한도: 이후로는 부르지 않는다
        QUOTA_HIT = True
        return {"uncalled": True}
    if code == "500":  # 키·IP 인증 실패: 멈춘다
        raise RuntimeError(f"ODsay {code}: {(err[0] if isinstance(err, list) else err).get('message')}")
    p.write_text(json.dumps(data, ensure_ascii=False))
    time.sleep(0.15)
    return data


def best(data: dict) -> tuple[float, str]:
    if data.get("uncalled"):
        return np.nan, "미호출"
    paths = data.get("result", {}).get("path", [])
    if not paths:
        return np.nan, ""
    p = min(paths, key=lambda x: x["info"]["totalTime"])
    legs = [(s.get("lane", [{}])[0].get("busNo") or s.get("lane", [{}])[0].get("name", "")) for s in p["subPath"] if s["trafficType"] != 3]
    return float(p["info"]["totalTime"]), " → ".join(legs)


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    areas = gpd.read_file(REPO / "commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    rep = areas.to_crs(5179).representative_point().to_crs(4326)
    areas["lat"], areas["lon"] = rep.y, rep.x
    d = np.hypot((areas.lat - CAMPUS[0]) * 111, (areas.lon - CAMPUS[1]) * 88.2)
    areas["straight_km"] = d.round(2)
    areas["reach_min"], areas["route"] = np.nan, ""
    band = np.select([d.between(EST_IN_KM, EST_OUT_KM), d < EST_IN_KM], [0, 1], 2)  # 부르는 순서: 4~8km → 4km 안 → 8km 밖
    for i, r in areas.assign(band=band, dist=d)[d <= MAX_STRAIGHT_KM].sort_values(["band", "dist"]).iterrows():
        m, route = (0.0, "도보") if r.straight_km <= 0.5 else best(odsay(r.lat, r.lon))
        if r.straight_km <= 1.0:  # 1km 안은 걸어가는 쪽도 비교 (직선×1.25, 시속 4.5km)
            m = min(m if not np.isnan(m) else np.inf, r.straight_km * 1.25 / 4.5 * 60)
        areas.loc[i, ["reach_min", "route"]] = [m, route]
    measured = areas.reach_min.notna()
    areas["reach_status"] = np.select([measured, d <= EST_IN_KM, d > EST_OUT_KM], ["측정", "추정 안(4km 이하)", "추정 밖(8km 초과)"], "미측정(4~8km)")
    score = pd.read_csv(REPO / "food_shopping_v1/official_area_food_shopping_v1_786.csv", dtype={"area_code": str})
    tags = pd.read_csv(REPO / "appendix_discovery_tags/official_area_discovery_tags_786.csv", dtype={"area_code": str})
    keep = ["area_code", "food_score", "shopping_score", "cafe_score_provisional", "best_subtype_score"] + \
           [f"{s}_score" for s in ["M1", "M2", "M3", "M4", "M5", "M6", "SH1", "SH2", "SH3", "SH4", "SH5"]]
    out = areas.drop(columns="geometry").assign(area_code=areas.area_code.astype(str)).merge(score[keep], on="area_code", how="left") \
        .merge(tags[["area_code", "primary_district_name", "discovery_tags", "purpose_driven", "young_tag", "evening_tag",
                     "weekend_tag", "specialty_mix", "dominant_industry", "official_store_count_q4"]], on="area_code", how="left")
    tags = pd.read_csv(OUT / "seoulcampus_area_tags_v1.csv", dtype={"area_code": str}).drop(columns="area_name")
    out = out.merge(tags, on="area_code", how="left")
    out["wait_risk"] = out.reach_min.between(WAIT_RISK_MIN, REACH_MIN, inclusive="right")
    print("status", out.reach_status.value_counts().to_dict())
    reach = out[(out.reach_min <= REACH_MIN) | (out.reach_status == "추정 안(4km 이하)")].copy()
    for c in ["food_score", "shopping_score", "cafe_score_provisional"]:
        reach[c.replace("_score", "").replace("_provisional", "") + "_pct_in_30min"] = reach[c].rank(pct=True).mul(100).round(1)
    reach.sort_values("food_score", ascending=False).to_csv(OUT / "seoulcampus_areas_reach_v1.csv", index=False, encoding="utf-8-sig")
    print("areas", len(out), "within 30 min (측정+추정 안)", len(reach), "측정", int(reach.reach_min.le(REACH_MIN).sum()))
    cols = ["area_name", "area_type_name", "primary_district_name", "reach_min", "reach_status", "discovery_tags",
            "n_nopo", "n_old_cafe", "n_goodprice"]
    base = set(reach.nlargest(TOP_N, "food_score").area_code)
    for m in SENS_MIN:  # 30분 기준 민감도: 도달 상권 수와 식사 상위 10 겹침
        r = out[out.reach_min <= m]
        print(f"sens {m}min areas {len(r)} food_top10_overlap {len(base & set(r.nlargest(TOP_N, 'food_score').area_code))}")
    print("wait_risk in 30min", int(reach.wait_risk.sum()))
    hide = ["n_nopo", "n_10yr", "n_old_cafe", "n_goodprice"]
    print("\n== 숨은 가게 태그 많은 상권\n", reach.assign(n_hidden=reach[hide].sum(axis=1)).nlargest(TOP_N, "n_hidden")[cols + ["n_hidden"]].to_string(index=False))
    for c in ["food_score", "shopping_score", "cafe_score_provisional"]:
        print(f"\n== {c}\n", reach.nlargest(TOP_N, c)[cols + [c]].to_string(index=False))
    hidden = reach[reach.purpose_driven.fillna(False).astype(bool) | reach.young_tag.fillna(False).astype(bool)]
    print("\n== 발견 태그(목적형·청년형)", len(hidden), "\n", hidden.sort_values("reach_min")[cols].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
