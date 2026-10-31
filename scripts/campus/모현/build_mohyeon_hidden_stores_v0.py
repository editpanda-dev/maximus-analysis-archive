"""모현(글캠) 30분 안 '숨은 가게' 목록 v0.

인기도·리뷰 없이 공공데이터만으로 고른다(대회 규정상 리뷰 수집 금지).
    대상   = SBIZ 2026-06 음식(I2)·예술·스포츠(R1)·취미문화 소매(SH4 코드+서점) 점포 중 도달 30분 이내
    도달   = static_transit_reach 모델(스코어카드 v0와 같은 보정값)
    태그
      노포       = 2005년 이전 인허가·영업 중 일반음식점과 80m 안에서 상호가 같거나 비슷(difflib 0.6)한 SBIZ 점포
      노포 후보  = 2005년 이전 인허가인데 지금 SBIZ에 같은 상호가 안 보이는 곳(지위승계·이름 변경 가능)
      개인카페   = 카페·빵·디저트 중 프랜차이즈가 아닌 곳
      희소 업종  = 30분 안에 2곳 이하인 음식·여가 소분류 (구내식당·유흥·복권 등 제외)
    프랜차이즈 = 지점명이 있거나, 캠퍼스 20km 안에 5번 이상 나오는 상호(3글자 이상)로 시작하는 곳
실행: ~/.venvs/maximus/bin/python 분석/모현/build_mohyeon_hidden_stores_v0.py  (스코어카드 v0 먼저)
"""

from __future__ import annotations

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_mohyeon_scorecard_v0 import NOPO_YEAR, OUT, RAW, REACH_MIN, SUBTYPES  # noqa: E402
from static_transit_reach import BusNetwork, calibrate  # noqa: E402

MAX_KM = 8  # 30분 안 군집은 모두 직선 5.5km 안
NAME_MATCH_M = 80
NAME_SIMILARITY = 0.6
FRANCHISE_MIN_COUNT = 5
RARE_MAX = 2
# 접두어 규칙으로 안 잡힌 체인(상호 앞에 지점명이 붙거나 20km 안 5곳 미만). 2026-10-30 목록 눈검사로 추가
KNOWN_CHAINS = {"달리는커피", "탐앤탐스", "메가커피", "메가엠지씨", "파니스안젤리쿠스", "행복한찹쌀꽈베기",
                "그로서리커피", "쮸커커피", "골든어스", "던킨", "파리바게뜨", "뚜레쥬르", "신불떡볶이", "와플대학",
                "100년에프앤비", "꽈백최선생"}
HOBBY_RETAIL = SUBTYPES["SH4"][2] | {"G21301", "G21302"}  # 취미·문화 + 서점·중고서점
CAFE_CODES = SUBTYPES["CF"][2]
NOT_INTERESTING = {"구내식당", "복권 발행/판매업", "일반 유흥 주점", "무도 유흥 주점", "기타 주점", "기타 오락장"}


BRANCH_SUFFIX = re.compile(r"(용인외대|외대|모현|용인|오포|경기광주|광주|매산|포곡|능평|신현|양벌|문형|추자|태전|본)점$")


def norm(name) -> str:
    """상호 비교용: 괄호·공백과 이 지역 지점 꼬리('용인외대점' 등) 제거."""
    s = re.sub(r"\(.*?\)|\s", "", str(name))
    return BRANCH_SUFFIX.sub("", s) or s


def is_franchise(key: str, brands: set[str]) -> bool:
    """'던킨도너츠한국외대글로벌캠퍼스점'처럼 브랜드 뒤에 지점명이 붙어도 잡는다(3글자 이상 브랜드 접두어)."""
    return any(key[:n] in brands for n in range(3, len(key) + 1)) or any(c in key for c in KNOWN_CHAINS)


def similar(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a in b or b in a or SequenceMatcher(None, a, b).ratio() >= NAME_SIMILARITY)


def main() -> None:
    raw = pd.read_csv(RAW / "sbiz_stores_within20km_globalcampus_202606.csv", dtype=str)
    raw["key"] = raw["상호명"].map(norm)
    franchise_names = set(raw.key.value_counts().loc[lambda s: s >= FRANCHISE_MIN_COUNT].index)
    raw["dist"] = raw.dist_km_from_globalcampus.astype(float)
    s = raw[raw.dist <= MAX_KM].copy()
    s[["경도", "위도"]] = s[["경도", "위도"]].astype(float)
    code = s["상권업종소분류코드"]
    s = s[(s["상권업종대분류코드"].isin(["I2", "R1"])) | code.isin(HOBBY_RETAIL)].copy()

    targets = pd.read_csv(OUT / "mohyeon_reach_calibration_v0.csv").drop(columns="est_min")
    net = BusNetwork()
    best, _ = calibrate(net, targets)
    stop_min = net.stop_times(best["local_kmh"], best["express_kmh"], best["transfer_min"])
    s["reach_min"] = net.to_points(stop_min, s["위도"], s["경도"]).round(1)
    s = s[s.reach_min <= REACH_MIN].copy()
    s["franchise"] = s["지점명"].notna() | s.key.map(lambda k: is_franchise(k, franchise_names))
    pts = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s["경도"], s["위도"]), crs=4326).to_crs(5179)

    # 노포: 인허가(좌표 없는 건 카카오 주소검색 좌표) ↔ SBIZ 상호
    lic = pd.read_csv(RAW / "인허가_일반음식점/general_restaurants_cheoin_gwangju_20261029.csv", dtype=str)
    lic = lic[lic.SALS_STTS_CD == "01"].copy()
    lic["year"] = pd.to_numeric(lic.LCPMT_YMD.str[:4], errors="coerce")
    lic = lic[lic.year <= NOPO_YEAR]
    geo = pd.read_csv(RAW / "인허가_일반음식점/kakao_geocode_missing_coords_20261029.csv", dtype={"MNG_NO": str}).dropna()
    has = lic.CRD_INFO_X.notna()
    a = gpd.GeoDataFrame(lic[has], geometry=gpd.points_from_xy(lic[has].CRD_INFO_X.astype(float), lic[has].CRD_INFO_Y.astype(float)), crs=5174).to_crs(5179)
    m = lic[~has].merge(geo, on="MNG_NO")
    b = gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(m.kakao_lon, m.kakao_lat), crs=4326).to_crs(5179)
    lic = pd.concat([a, b[a.columns]], ignore_index=True)
    lic["key"] = lic.BPLC_NM.map(norm)
    # 80m 안 모든 SBIZ 점포와 상호를 비교한다
    buf = lic.assign(lic_id=lic.index)
    buf["geometry"] = buf.buffer(NAME_MATCH_M)
    cand = gpd.sjoin(pts[["key", "geometry"]].assign(store_id=pts.index),
                     buf[["lic_id", "BPLC_NM", "key", "year", "geometry"]], predicate="within", lsuffix="s", rsuffix="l")
    cand = cand[[similar(x, y) for x, y in zip(cand.key_s, cand.key_l)]]
    first = cand.sort_values("year").drop_duplicates("store_id").set_index("store_id")
    s["license_year"] = first.year.reindex(s.index)
    s["license_name"] = first.BPLC_NM.reindex(s.index)
    s["nopo"] = s.license_year.notna() & ~s.franchise
    reach_lic = lic.to_crs(4326)
    reach_lic["reach_min"] = net.to_points(stop_min, reach_lic.geometry.y, reach_lic.geometry.x).round(1)
    nopo_maybe = reach_lic[(reach_lic.reach_min <= REACH_MIN) & ~reach_lic.index.isin(set(cand.lic_id))]
    nopo_maybe = nopo_maybe[~nopo_maybe.key.map(lambda k: is_franchise(k, franchise_names))]
    nopo_maybe[["BPLC_NM", "LCPMT_YMD", "reach_min"]].assign(
        lat=nopo_maybe.geometry.y, lon=nopo_maybe.geometry.x).sort_values("LCPMT_YMD").to_csv(
        OUT / "mohyeon_nopo_candidates_unmatched_v0.csv", index=False, encoding="utf-8-sig")

    s["indie_cafe"] = s["상권업종소분류코드"].isin(CAFE_CODES) & ~s.franchise
    leisure = s[~s["상권업종소분류명"].isin(NOT_INTERESTING)]
    counts = leisure["상권업종소분류명"].value_counts()
    s["rare_type"] = s["상권업종소분류명"].map(counts).le(RARE_MAX) & ~s["상권업종소분류명"].isin(NOT_INTERESTING) & ~s.franchise

    # 스코어카드 군집 번호 붙이기
    clusters = gpd.read_file(OUT / "mohyeon_scorecard_v0.geojson").to_crs(5179)[["cluster", "geometry"]]
    s["cluster"] = gpd.sjoin(pts[["geometry"]], clusters, predicate="within").cluster.reindex(s.index)

    out = s[s.nopo | s.indie_cafe | s.rare_type]
    cols = ["상호명", "상권업종소분류명", "nopo", "license_year", "license_name", "indie_cafe", "rare_type", "reach_min",
            "cluster", "행정동명", "도로명주소", "층정보", "위도", "경도"]
    out[cols].sort_values(["nopo", "rare_type", "reach_min"], ascending=[False, False, True]).to_csv(
        OUT / "mohyeon_hidden_stores_v0.csv", index=False, encoding="utf-8-sig")
    print("reachable stores", len(s), "| nopo", int(s.nopo.sum()), "| indie cafe", int(s.indie_cafe.sum()),
          "| rare", int(s.rare_type.sum()), "| unmatched old licenses", len(nopo_maybe))


if __name__ == "__main__":
    main()
