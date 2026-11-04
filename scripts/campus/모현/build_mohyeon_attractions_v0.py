"""모현(글캠) 30분 안 명소 목록 v0와 상권 스코어카드 연결.

    대상   = 카카오 로컬 AT4(관광명소)·CT1(문화시설) 2,161곳 + 도시공원 표준데이터(용인·광주 406)
             + 공공시설 개방 표준데이터(용인·광주 133, 체육·대관) + TourAPI 반경 20km(관광지·문화·레포츠·쇼핑)
             + 국민체육진흥공단 전국체육시설 중 용인·광주 공공·정상운영. 어린이공원·소공원도 minor_place.
             번지 없는 산·계곡 이름은 minor_place로 표시(지명에 가까움), 직선 도보로만 닿는 1km 밖은 카카오 보행경로로 실측(없으면 길 확인 필요)
    도달   = static_transit_reach 모델(스코어카드 v0와 같은 보정값). 30분 이내만, 26~34분은 경계 표시
    유형   = 카카오 3단계 분류를 자연·산책 / 전시·문화 / 공연·영화 / 체험·놀거리로 묶음
    연결   = 30분 안 상권 군집마다 1km 안 명소 수·이름 (상권 + 명소 코스용)

인기도·리뷰는 쓰지 않는다(대회 규정상 리뷰 수집 금지). 산·계곡 좌표는 정상·계곡 지점이라
버스에서 내려 걷는 거리가 실제 등산로 입구와 다를 수 있다.
실행: ~/.venvs/maximus/bin/python 분석/모현/build_mohyeon_attractions_v0.py  (스코어카드 v0 먼저)
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_mohyeon_scorecard_v0 import BORDER_MIN, OUT, RAW, REACH_MIN, haversine_km  # noqa: E402
from static_transit_reach import WALK_DETOUR, WALK_KMH, BusNetwork, calibrate  # noqa: E402

NEAR_CLUSTER_M = 1000
WALK_CHECK_KM = 1.0
MINOR_CATEGORIES = {"산", "계곡"}
# TourAPI 콘텐츠 유형(음식점 39·숙박 32는 명소가 아니라 뺀다)
TOUR_TYPES = {12: "관광지", 14: "문화시설", 28: "레포츠", 38: "쇼핑"}
SMALL_PARKS = {"어린이공원", "소공원"}  # 동네 놀이터 수준이라 대표 명소에서는 뺀다
TYPES = {
    "자연·산책": {"산", "계곡", "저수지", "호수", "숲", "수목원,식물원", "자연휴양림", "도립공원", "도보여행",
              "자전거여행", "드라이브코스", "섬", "전망대"},
    "전시·문화": {"전시관", "미술관", "박물관", "기념관", "과학관", "문화원", "문화유적", "천문대", "민속촌"},
    "공연·영화": {"공연장,연극극장", "영화관"},
    "체험·놀거리": {"도자기,도예촌", "테마파크", "관광농원", "동물원", "눈썰매장", "온천", "유원지", "아쿠아리움",
               "관광단지", "테마거리"},
}
TYPE_OF = {c: t for t, cats in TYPES.items() for c in cats}


def load_places() -> pd.DataFrame:
    """카카오 명소 + 도시공원 표준데이터 + 공공시설 개방 표준데이터를 같은 열로 합친다."""
    k = pd.read_csv(RAW / "kakao_attractions_culture_20km.csv")
    parts = k.category_name.str.split(" > ")
    k["category"] = parts.str[2].fillna(parts.str[1])
    k["type"] = k.category.map(TYPE_OF).fillna("기타")
    k["source"] = "카카오"
    k["note"] = ""
    std = RAW / "표준데이터"
    p = pd.read_csv(std / "city_parks_yongin_gwangju_15012890.csv").dropna(subset=["위도", "경도"])
    p = pd.DataFrame({
        "place_name": p["공원명"], "category": p["공원구분"], "type": "자연·산책", "source": "도시공원",
        "address_name": p["소재지지번주소"].fillna(p["소재지도로명주소"]), "x": p["경도"], "y": p["위도"], "place_url": "",
        "note": p[[c for c in p.columns if c.startswith("공원보유시설")]].fillna("").agg(" ".join, axis=1).str.strip(),
    })
    o = pd.read_csv(std / "public_facility_open_yongin_gwangju_15013117.csv").dropna(subset=["위도", "경도"])
    o = pd.DataFrame({
        "place_name": o["개방시설명"], "category": o["개방시설유형구분"], "type": "체육·대관", "source": "공공시설개방",
        "address_name": o["소재지지번주소"].fillna(o["소재지도로명주소"]), "x": o["경도"], "y": o["위도"],
        "place_url": o["홈페이지주소"].fillna(""),
        "note": "평일 " + o["평일운영시작시각"].astype(str) + "~" + o["평일운영종료시각"].astype(str)
                + " · 유료 " + o["유료사용여부"].astype(str),
    })
    ts = RAW / "관광_체육"
    t = pd.read_csv(ts / "tourapi_location_20km_20261030.csv")
    t = t[t.contenttypeid.isin(TOUR_TYPES)]
    t = pd.DataFrame({
        "place_name": t.title, "category": t.contenttypeid.map(TOUR_TYPES), "source": "TourAPI",
        "type": t.contenttypeid.map({12: "관광지", 14: "전시·문화", 28: "체험·놀거리", 38: "쇼핑"}).replace({"관광지": "자연·산책"}),
        "address_name": t.addr1, "x": t.mapx, "y": t.mapy, "place_url": "", "note": t.cat3,
    })
    sp = pd.read_csv(ts / "sports_facilities_yongin_gwangju_20261030.csv")
    sp = sp[(sp.faci_stat_nm == "정상운영") & (sp.faci_gb_nm == "공공")].dropna(subset=["faci_lat", "faci_lot"])
    sp = pd.DataFrame({
        "place_name": sp.faci_nm, "category": sp.ftype_nm, "type": "체육·대관", "source": "공공체육시설",
        "address_name": sp.faci_road_addr.fillna(sp.faci_addr), "x": sp.faci_lot, "y": sp.faci_lat, "place_url": "",
        "note": sp.inout_gbn_nm.fillna(""),
    })
    return pd.concat([k, p, o, t, sp], ignore_index=True).drop_duplicates(["place_name", "category"])


def main() -> None:
    k = load_places()

    # 스코어카드가 저장한 보정 기준(ODsay 실측)으로 같은 보정값을 다시 구한다
    targets = pd.read_csv(OUT / "mohyeon_reach_calibration_v0.csv").drop(columns="est_min")
    net = BusNetwork()
    best, _ = calibrate(net, targets)
    stop_min = net.stop_times(best["local_kmh"], best["express_kmh"], best["transfer_min"])
    k["reach_min"] = net.to_points(stop_min, k.y, k.x).round(1)
    k["straight_km"] = haversine_km(k.y, k.x).round(2)
    k["reach_band"] = np.select(
        [k.reach_min <= REACH_MIN - BORDER_MIN, k.reach_min <= REACH_MIN, k.reach_min <= REACH_MIN + BORDER_MIN],
        ["안쪽", "경계(안)", "경계(밖)"], default="밖")
    # 버스보다 직선 도보가 빠르게 나온 곳: 산·능선을 넘는 직선일 수 있어 실제 길 확인 전엔 30분 안으로 치지 않는다
    walk_direct = (k.straight_km * 1000 * WALK_DETOUR / (WALK_KMH * 1000) * 60).round(1)
    k["walk_only"] = (k.reach_min >= walk_direct - 0.2) & (k.straight_km > WALK_CHECK_KM)
    # 카카오 보행경로로 실제 걸어본 곳은 그 시간으로 바꾼다 (2026-10-29: 산을 돌아가 59~241분)
    checked = OUT / "mohyeon_attractions_walkcheck_v0.csv"
    if checked.exists():
        real = k.place_name.map(pd.read_csv(checked).dropna(subset=["walk_min"]).set_index("place_name").walk_min)
        fix = k.walk_only & real.notna()
        k.loc[fix, "reach_min"] = real[fix]
        k.loc[fix, "walk_only"] = False
        k.loc[fix, "reach_band"] = np.where(real[fix] <= REACH_MIN, "안쪽(도보 실측)", "밖(도보 실측)")
    k.loc[k.walk_only & (k.reach_band != "밖"), "reach_band"] = "도보 길 확인 필요"
    # 번지 없는 산·계곡 이름은 지도상 지명에 가깝다. 목록에는 두되 상권 연결과 대표 명소에서는 뺀다
    k["minor_place"] = (k.category.isin(MINOR_CATEGORIES) & ~k.address_name.str.contains(r"\d", na=False)) | k.category.isin(SMALL_PARKS)
    near = k[k.reach_min <= REACH_MIN + BORDER_MIN].sort_values("reach_min")
    cols = ["place_name", "source", "type", "category", "note", "reach_min", "reach_band", "walk_only", "minor_place", "straight_km", "address_name", "x", "y", "place_url"]
    near[cols].to_csv(OUT / "mohyeon_attractions_reach_v0.csv", index=False, encoding="utf-8-sig")
    print("within 34 min", len(near), near.groupby(["reach_band", "type"]).size().unstack(fill_value=0).to_string(), sep="\n")

    # 상권 군집마다 1km 안 명소 (30분 안 명소만)
    card = pd.read_csv(OUT / "mohyeon_scorecard_v0.csv")
    geo = gpd.read_file(OUT / "mohyeon_scorecard_v0.geojson").to_crs(5179)[["cluster", "geometry"]]
    geo["geometry"] = geo.buffer(NEAR_CLUSTER_M)
    inside = near[(near.reach_min <= REACH_MIN) & ~near.walk_only & ~near.minor_place]
    pts = gpd.GeoDataFrame(inside, geometry=gpd.points_from_xy(inside.x, inside.y), crs=4326).to_crs(5179)
    j = gpd.sjoin(pts[["place_name", "type", "geometry"]], geo, predicate="within")
    card = card.drop(columns=[c for c in card.columns if c.startswith("attr_")])
    card["attr_1km_count"] = card.cluster.map(j.groupby("cluster").size()).fillna(0).astype(int)
    for t in [*TYPES, "체육·대관"]:
        card[f"attr_1km_{t}"] = card.cluster.map(j[j.type == t].groupby("cluster").size()).fillna(0).astype(int)
    card["attr_1km_names"] = card.cluster.map(j.groupby("cluster").place_name.apply(lambda s: ", ".join(s.head(6))))
    card.to_csv(OUT / "mohyeon_scorecard_v0.csv", index=False, encoding="utf-8-sig")
    print(card[["cluster", "dong", "landmark", "attr_1km_count", "attr_1km_names"]].to_string(index=False))


if __name__ == "__main__":
    main()
