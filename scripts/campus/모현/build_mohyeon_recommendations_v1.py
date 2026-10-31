"""모현(글캠) 추천 목록 v1: 가게 + 공공 명소를 도달 단계별로 합친다.

v0(30분 안 숨은 가게 171·명소 39)이 빈약해서 범위와 태그를 넓혔다. 2026-10-30 사용자 결정: 45분 확장은 빼고 '차 30분'을 넣는다.
    도달 단계 (앞 단계에 들면 뒤 단계로 세지 않음)
      대중교통 30분 = 대기 없는 추정 30분 이내 (ODsay 정의)
      차 30분       = 카카오모빌리티 길찾기 30분 이내(택시·자가용). 가게는 가장 가까운 측정점(1.5km 안) 시간 + 남은 직선 ÷ 20km/h.
                     택시요금 함께 표시 (build_mohyeon_car_reach_v1.py)
      셔틀(평일)    = 학교 통학버스 판교·서현 노선 하교편(14:10~18:20 출발)으로 가는 서현역·성남역·판교역 600m 안.
                     시간 = 셔틀 소요(45·48·50분) + 도보. 무료(한시적). 돌아오는 셔틀은 아침 등교편뿐
      reach_wait    = 노선 배차 절반(최대 30분)을 기다린다고 본 시간. 참고용
    태그(가게)
      노포(2005 이전)·10년+ 가게(2006~2015) = 인허가와 80m 안 상호 일치(유사도 0.6)
      개인카페 = 카페·빵·떡 중 프랜차이즈 아님
      희소 업종 = 해당 단계 안에 2곳 이하인 음식·여가 소분류
      관광공사 소개 = TourAPI 음식점(39)과 80m 안 상호 일치
      착한가격 = 행안부 착한가격업소(goodprice.go.kr 전국 엑셀, 용인·광주·성남 음식 업종)와 80m 안 상호 일치.
                 SBIZ에 없는 착한가격업소는 그 자체로 한 줄 추가. 대표 품목·가격은 note에
      인허가 = 일반음식점 + 휴게음식점(카페 등) + 제과점, 용인 전체·광주·성남 전체
    명소 = build_mohyeon_attractions_v0와 같은 원천(카카오·도시공원·공공시설개방·TourAPI·공공체육), minor_place 제외
실행: ~/.venvs/maximus/bin/python 분석/모현/build_mohyeon_recommendations_v1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_mohyeon_attractions_v0 as at  # noqa: E402
from build_mohyeon_hidden_stores_v0 import (  # noqa: E402
    CAFE_CODES, FRANCHISE_MIN_COUNT, HOBBY_RETAIL, NAME_MATCH_M, NOT_INTERESTING, RARE_MAX, is_franchise, norm, similar)
from build_mohyeon_scorecard_v0 import OUT, RAW  # noqa: E402
from static_transit_reach import BusNetwork, calibrate, walk_min  # noqa: E402

TIER_30 = 30
CAR_SNAP_M, CAR_TAIL_KMH = 1500, 20
NOPO_YEAR, TENURE_YEAR = 2005, 2015
SHUTTLE_WALK_M = 600
# 2026-2학기 통학버스 판교·서현 노선 하교편: 캠퍼스 출발 14:10·15:10·15:25·17:30·18:20 (2026-10-19~12-21, 평일)
SHUTTLE_STOPS = {  # 정류장: (위도, 경도, 캠퍼스에서 분) — 좌표는 카카오 키워드 검색
    "서현역 5번출구": (37.38555, 127.12381, 45),
    "성남역(백현마을3단지)": (37.38989, 127.11772, 48),
    "판교역 1번출구": (37.39526, 127.11149, 50),
}
SHUTTLE_NOTE = "통학버스 판교·서현 하교편 평일 14:10/15:10/15:25/17:30/18:20, 한시적 무료, 복귀 셔틀 없음"
LICENSE_FILES = ["인허가_일반음식점/general_restaurants_cheoin_gwangju_20261029.csv",  # 4050000=용인 전체 + 광주
                 "인허가_일반음식점/general_restaurants_bundang_20261030.csv",  # 3780000=성남 전체
                 "인허가_휴게제과/rest_cafes_yongin_gwangju_seongnam_20261030.csv",
                 "인허가_휴게제과/bakeries_yongin_gwangju_seongnam_20261030.csv"]
GEOCODE_FILES = ["인허가_일반음식점/kakao_geocode_missing_coords_20261029.csv",
                 "인허가_휴게제과/kakao_geocode_missing_coords_20261030.csv"]
FOOD_INDUSTRIES = {"한식", "중식", "일식", "양식", "베이커리", "기타요식업"}


def shuttle_min(lat, lon) -> np.ndarray:
    best = np.full(len(lat), np.inf)
    for s_lat, s_lon, m in SHUTTLE_STOPS.values():
        d = np.hypot((np.asarray(lat) - s_lat) * 111_000, (np.asarray(lon) - s_lon) * 88_600)
        best = np.minimum(best, np.where(d <= SHUTTLE_WALK_M, m + walk_min(d), np.inf))
    return best


def tier(reach, car, shuttle) -> np.ndarray:
    return np.select([reach <= TIER_30, car <= TIER_30, np.isfinite(shuttle)], ["대중교통 30분", "차 30분", "셔틀(평일)"], default="")


def car_estimate(lat, lon, probes: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """가장 가까운 차 측정점 시간·택시요금 + 남은 직선거리 몫. 1.5km 안에 측정점이 없으면 inf."""
    from scipy.spatial import cKDTree
    pr = probes.dropna(subset=["car_min"])
    xy = lambda la, lo: np.c_[np.asarray(lo, float) * 88_600, np.asarray(la, float) * 111_000]
    d, i = cKDTree(xy(pr.lat, pr.lon)).query(xy(lat, lon))
    minutes = pr.car_min.to_numpy()[i] + d / (CAR_TAIL_KMH * 1000) * 60
    return np.where(d <= CAR_SNAP_M, minutes, np.inf).round(1), np.where(d <= CAR_SNAP_M, pr.taxi_won.to_numpy()[i], np.nan)


def licenses() -> gpd.GeoDataFrame:
    frames = []
    for f in LICENSE_FILES:
        frames.append(pd.read_csv(RAW / f, dtype=str))
    lic = pd.concat(frames, ignore_index=True).drop_duplicates("MNG_NO")
    lic = lic[lic.SALS_STTS_CD == "01"].copy()
    lic["year"] = pd.to_numeric(lic.LCPMT_YMD.str[:4], errors="coerce")
    lic = lic[lic.year <= TENURE_YEAR]
    has = lic.CRD_INFO_X.notna()
    a = gpd.GeoDataFrame(lic[has], geometry=gpd.points_from_xy(lic[has].CRD_INFO_X.astype(float), lic[has].CRD_INFO_Y.astype(float)), crs=5174).to_crs(5179)
    geo = pd.concat([pd.read_csv(RAW / f, dtype={"MNG_NO": str}) for f in GEOCODE_FILES])[["MNG_NO", "kakao_lat", "kakao_lon"]].dropna()
    m = lic[~has].merge(geo.drop_duplicates("MNG_NO"), on="MNG_NO")
    b = gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(m.kakao_lon, m.kakao_lat), crs=4326).to_crs(5179)
    out = pd.concat([a, b[a.columns]], ignore_index=True)
    out["key"] = out.BPLC_NM.map(norm)
    return out


def goodprice() -> gpd.GeoDataFrame:
    """착한가격업소(행안부 goodprice.go.kr 전국 엑셀 중 용인·광주·성남) 음식 업종만, 카카오 좌표."""
    d = RAW / "착한가격업소"
    gp = pd.read_csv(d / "goodprice_yongin_gwangju_seongnam_20261030.csv", dtype=str).merge(
        pd.read_csv(d / "kakao_geocode_goodprice_yongin_gwangju_seongnam_20261030.csv", dtype=str), on="번호").dropna(subset=["kakao_lat"])
    gp = gp[gp.업종명.isin(FOOD_INDUSTRIES)]
    gp = pd.DataFrame({"name": gp.업소명, "address": gp.주소, "items": gp.주요품목.str.strip() + " " + gp.가격.str.strip(),
                       "lat": gp.kakao_lat.astype(float), "lon": gp.kakao_lon.astype(float)})
    gp["key"] = gp.name.map(norm)
    return gpd.GeoDataFrame(gp, geometry=gpd.points_from_xy(gp.lon, gp.lat), crs=4326).to_crs(5179)


def name_match(pts: gpd.GeoDataFrame, ref: gpd.GeoDataFrame, cols: list[str]) -> pd.DataFrame:
    """점포(pts.key)와 80m 안 ref(key) 상호가 같거나 비슷한 첫 행."""
    buf = ref.assign(ref_id=ref.index)
    buf["geometry"] = buf.buffer(NAME_MATCH_M)
    c = gpd.sjoin(pts[["key", "geometry"]].assign(store_id=pts.index), buf[["ref_id", "key", *cols, "geometry"]],
                  predicate="within", lsuffix="s", rsuffix="r")
    c = c[[similar(x, y) for x, y in zip(c.key_s, c.key_r)]]
    return c.drop_duplicates("store_id").set_index("store_id")


def main() -> None:
    raw = pd.read_csv(RAW / "sbiz_stores_within20km_globalcampus_202606.csv", dtype=str)
    raw["key"] = raw["상호명"].map(norm)
    brands = set(raw.key.value_counts().loc[lambda s: s >= FRANCHISE_MIN_COUNT].index)
    raw[["경도", "위도"]] = raw[["경도", "위도"]].astype(float)
    code = raw["상권업종소분류코드"]
    s = raw[raw["상권업종대분류코드"].isin(["I2", "R1"]) | code.isin(HOBBY_RETAIL)].copy()

    net = BusNetwork()
    best, _ = calibrate(net, pd.read_csv(OUT / "mohyeon_reach_calibration_v0.csv").drop(columns="est_min"))
    args = (best["local_kmh"], best["express_kmh"], best["transfer_min"])
    stop0, stop1 = net.stop_times(*args), net.stop_times(*args, wait=True)
    s["shuttle_min"] = shuttle_min(s["위도"], s["경도"])
    probes = pd.read_csv(OUT / "mohyeon_car_reach_v1.csv")
    s["reach_min"] = net.to_points(stop0, s["위도"], s["경도"]).round(1)
    s["reach_wait"] = net.to_points(stop1, s["위도"], s["경도"]).round(1)
    s["car_min"], s["taxi_won"] = car_estimate(s["위도"], s["경도"], probes)
    s["tier"] = tier(s.reach_min, s.car_min, s.shuttle_min)
    s = s[s.tier != ""].copy()
    s["franchise"] = s["지점명"].notna() | s.key.map(lambda k: is_franchise(k, brands))
    pts = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s["경도"], s["위도"]), crs=4326).to_crs(5179)

    lic = licenses()
    hit = name_match(pts, lic, ["year", "BPLC_NM"])
    s["license_year"] = hit.year.reindex(s.index)
    s["license_name"] = hit.BPLC_NM.reindex(s.index)
    tour = pd.read_csv(RAW / "관광_체육/tourapi_location_20km_20261030.csv")
    tour = tour[tour.contenttypeid == 39]
    tour = gpd.GeoDataFrame(tour.assign(key=tour.title.map(norm)), geometry=gpd.points_from_xy(tour.mapx, tour.mapy), crs=4326).to_crs(5179)
    s["tourapi"] = s.index.isin(name_match(pts, tour, ["title"]).index)
    gp = goodprice()
    gp_hit = name_match(pts, gp, ["items"])
    s["goodprice_items"] = gp_hit["items"].reindex(s.index)

    indep = ~s.franchise
    s["tag_nopo"] = indep & (s.license_year <= NOPO_YEAR)
    s["tag_10yr"] = indep & s.license_year.between(NOPO_YEAR + 1, TENURE_YEAR)
    s["tag_indie_cafe"] = indep & s["상권업종소분류코드"].isin(CAFE_CODES)
    ok = ~s["상권업종소분류명"].isin(NOT_INTERESTING)
    counts = s[ok].groupby(["tier", "상권업종소분류명"]).size()
    s["tag_rare"] = indep & ok & np.array([counts.get((t, c), 0) <= RARE_MAX for t, c in zip(s.tier, s["상권업종소분류명"])])
    s["tag_tourapi"] = s.tourapi
    s["tag_goodprice"] = s.goodprice_items.notna()
    tags = ["tag_nopo", "tag_10yr", "tag_indie_cafe", "tag_rare", "tag_tourapi", "tag_goodprice"]
    label = {"tag_nopo": "노포", "tag_10yr": "10년+", "tag_indie_cafe": "개인카페", "tag_rare": "희소업종", "tag_tourapi": "관광공사 소개",
             "tag_goodprice": "착한가격"}
    s["tags"] = s[tags].apply(lambda r: " · ".join(label[t] for t in tags if r[t]), axis=1)
    stores = s[s[tags].any(axis=1)]
    stores = pd.DataFrame({
        "name": stores["상호명"], "kind": "가게", "category": stores["상권업종소분류명"], "tags": stores.tags,
        "n_tags": stores[tags].sum(axis=1), "since": stores.license_year, "tier": stores.tier,
        "reach_min": stores.reach_min, "reach_wait": stores.reach_wait, "car_min": stores.car_min,
        "taxi_won": stores.taxi_won, "shuttle_min": stores.shuttle_min.round(1),
        "area": stores["시군구명"] + " " + stores["행정동명"], "address": stores["도로명주소"],
        "lat": stores["위도"], "lon": stores["경도"], "note": "착한가격: " + stores.goodprice_items,
    })
    # SBIZ 점포와 안 맞은 착한가격업소는 그 자체로 추가
    g = gp[~gp.index.isin(gp_hit.ref_id)].copy()
    g["reach_min"] = net.to_points(stop0, g.lat, g.lon).round(1)
    g["reach_wait"] = net.to_points(stop1, g.lat, g.lon).round(1)
    g["shuttle_min"] = shuttle_min(g.lat, g.lon)
    g["car_min"], g["taxi_won"] = car_estimate(g.lat, g.lon, probes)
    g["tier"] = tier(g.reach_min, g.car_min, g.shuttle_min)
    g = g[g.tier != ""]
    stores = pd.concat([stores, pd.DataFrame({
        "name": g.name, "kind": "가게", "category": "착한가격업소", "tags": "착한가격", "n_tags": 1, "since": np.nan, "tier": g.tier,
        "reach_min": g.reach_min, "reach_wait": g.reach_wait, "car_min": g.car_min, "taxi_won": g.taxi_won,
        "shuttle_min": g.shuttle_min.round(1), "area": g.address.str.split().str[1:3].str.join(" "), "address": g.address,
        "lat": g.lat, "lon": g.lon, "note": "착한가격: " + g["items"]})], ignore_index=True)

    # 공공 명소: 같은 원천, 지명성 산·계곡·어린이공원 제외
    p = at.load_places()
    p["reach_min"] = net.to_points(stop0, p.y, p.x).round(1)
    p["reach_wait"] = net.to_points(stop1, p.y, p.x).round(1)
    p["shuttle_min"] = shuttle_min(p.y, p.x)
    p["car_min"], p["taxi_won"] = car_estimate(p.y, p.x, probes)
    p["tier"] = tier(p.reach_min, p.car_min, p.shuttle_min)
    minor = (p.category.isin(at.MINOR_CATEGORIES) & ~p.address_name.str.contains(r"\d", na=False)) | p.category.isin(at.SMALL_PARKS)
    walk_check = pd.read_csv(OUT / "mohyeon_attractions_walkcheck_v0.csv")
    far_on_foot = p.place_name.isin(walk_check[walk_check.walk_min > TIER_30].place_name)  # 실측 도보 30분 넘는 곳(대중교통 단계에서만 뺌)
    p.loc[far_on_foot & (p.tier == "대중교통 30분"), "tier"] = np.where(p.loc[far_on_foot & (p.tier == "대중교통 30분"), "car_min"] <= TIER_30, "차 30분", "")
    p = p[(p.tier != "") & ~minor]
    places = pd.DataFrame({
        "name": p.place_name, "kind": "명소", "category": p.category, "tags": p.type + " (" + p.source + ")",
        "n_tags": 1, "since": np.nan, "tier": p.tier, "reach_min": p.reach_min, "reach_wait": p.reach_wait,
        "car_min": p.car_min, "taxi_won": p.taxi_won, "shuttle_min": p.shuttle_min.round(1), "area": p.address_name.str.split().str[1:3].str.join(" "),
        "address": p.address_name, "lat": p.y, "lon": p.x,
    })
    rec = pd.concat([stores, places], ignore_index=True)
    # SBIZ에 같은 가게가 두 번 올라온 경우(같은 상호·50m 안)와 원천끼리 겹친 명소를 한 줄로
    rec = rec.assign(_k=rec.name.map(norm), _y=(rec.lat * 2000).round(), _x=(rec.lon * 1600).round()) \
        .drop_duplicates(["_k", "_y", "_x"]).drop(columns=["_k", "_y", "_x"])
    sh = rec.tier == "셔틀(평일)"
    rec.loc[sh, "note"] = rec.loc[sh, "note"].fillna("").radd(SHUTTLE_NOTE + " | ").str.rstrip(" |")
    order = {"대중교통 30분": 0, "차 30분": 1, "셔틀(평일)": 2}
    rec = rec.sort_values(["tier", "n_tags", "reach_min"], key=lambda c: c.map(order) if c.name == "tier" else c,
                          ascending=[True, False, True])
    rec.to_csv(OUT / "mohyeon_recommendations_v1.csv", index=False, encoding="utf-8-sig")
    summary = rec.assign(**{label[t]: rec.tags.str.contains(label[t]) for t in tags}).groupby(["tier", "kind"]).agg(
        items=("name", "size"), **{label[t]: (label[t], "sum") for t in tags})
    summary.to_csv(OUT / "mohyeon_recommendations_v1_summary.csv", encoding="utf-8-sig")
    print(summary.to_string())


if __name__ == "__main__":
    main()
