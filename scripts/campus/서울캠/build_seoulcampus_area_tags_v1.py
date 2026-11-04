"""서울캠 상권 786곳에 글캠 v1과 같은 '숨은 가게' 태그 수를 붙인다(도달시간과 무관, 상권 폴리곤 안 집계).

    인허가 = 행안부 일반음식점·휴게음식점·제과점 조회서비스, 서울 25개 구 영업 중(SALS_STTS_CD=01)만
    노포   = 2005 이전 인허가, 10년+ = 2006~2015, 오래된 카페·빵집 = 휴게음식점(커피숍·다방·과자점·전통찻집·떡카페)·제과점 중 2015 이전
    프랜차이즈 제외 = 상호 첫 단어가 서울 인허가에 5번 이상 나오거나, 상호가 5번 이상 나오는 이름으로 시작하거나, 글캠 KNOWN_CHAINS
    착한가격 = 행안부 착한가격업소(goodprice.go.kr 전국 엑셀) 서울 음식 업종, 카카오 좌표
출력: 데이터/가공/서울캠/seoulcampus_area_tags_v1.csv (area_code별 개수 + 대표 상호 3개)
실행: ~/.venvs/maximus/bin/python -I 분석/서울캠/build_seoulcampus_area_tags_v1.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "모현"))
from build_mohyeon_hidden_stores_v0 import FRANCHISE_MIN_COUNT, is_franchise, norm  # noqa: E402
from build_mohyeon_recommendations_v1 import FOOD_INDUSTRIES, NOPO_YEAR, TENURE_YEAR  # noqa: E402

RAW = ROOT / "데이터/원천/서울캠"
OUT = ROOT / "데이터/가공/서울캠"
AREAS = ROOT / "maximus-analysis-archive/data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"
SERVICES = ["general_restaurants", "rest_cafes", "bakeries"]
CAFE_TYPES = {"커피숍", "다방", "과자점", "전통찻집", "떡카페"}  # 휴게음식점 위생업태 중 카페·빵류


def licenses() -> gpd.GeoDataFrame:
    lic = pd.concat([pd.read_csv(RAW / f"인허가/{s}_seoul_active_20261030.csv", dtype=str).assign(service=s) for s in SERVICES],
                    ignore_index=True).drop_duplicates("MNG_NO")
    lic["year"] = pd.to_numeric(lic.LCPMT_YMD.str[:4], errors="coerce")
    lic["key"] = lic.BPLC_NM.map(norm)
    first = lic.BPLC_NM.str.split().str[0].fillna("")
    brands = set(lic.key.value_counts().loc[lambda s: s >= FRANCHISE_MIN_COUNT].index)
    lic["franchise"] = first.map(first.value_counts()).ge(FRANCHISE_MIN_COUNT) | lic.key.map(lambda k: is_franchise(k, brands))
    lic["cafe"] = lic.service.eq("bakeries") | (lic.service.eq("rest_cafes") & lic.SNTTN_BZSTAT_NM.fillna("").isin(CAFE_TYPES))
    lic = lic[lic.CRD_INFO_X.notna() & ~lic.franchise & (lic.year <= TENURE_YEAR)]
    return gpd.GeoDataFrame(lic, geometry=gpd.points_from_xy(lic.CRD_INFO_X.astype(float), lic.CRD_INFO_Y.astype(float)), crs=5174).to_crs(4326)


def goodprice() -> gpd.GeoDataFrame:
    gp = pd.read_csv(RAW / "착한가격업소/goodprice_seoul_20261030.csv", dtype=str).merge(
        pd.read_csv(RAW / "착한가격업소/kakao_geocode_goodprice_seoul_20261030.csv", dtype=str), on="번호").dropna(subset=["kakao_lat"])
    gp = gp[gp.업종명.isin(FOOD_INDUSTRIES)]
    return gpd.GeoDataFrame(gp, geometry=gpd.points_from_xy(gp.kakao_lon.astype(float), gp.kakao_lat.astype(float)), crs=4326)


def count(areas: gpd.GeoDataFrame, pts: gpd.GeoDataFrame, name_col: str, prefix: str) -> pd.DataFrame:
    j = gpd.sjoin(pts[[name_col, "geometry"]], areas[["area_code", "geometry"]], predicate="within")
    return j.groupby("area_code")[name_col].agg(**{f"n_{prefix}": "size", f"{prefix}_names": lambda s: " · ".join(s.head(3))})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    areas = gpd.read_file(AREAS)[["area_code", "area_name", "geometry"]].assign(area_code=lambda d: d.area_code.astype(str))
    lic = licenses()
    parts = [count(areas, lic[lic.year <= NOPO_YEAR], "BPLC_NM", "nopo"),
             count(areas, lic[lic.year.between(NOPO_YEAR + 1, TENURE_YEAR)], "BPLC_NM", "10yr"),
             count(areas, lic[lic.cafe], "BPLC_NM", "old_cafe"),
             count(areas, goodprice(), "업소명", "goodprice")]
    out = areas.drop(columns="geometry").set_index("area_code").join(parts)
    n = [c for c in out if c.startswith("n_")]
    out[n] = out[n].fillna(0).astype(int)
    out.reset_index().to_csv(OUT / "seoulcampus_area_tags_v1.csv", index=False, encoding="utf-8-sig")
    print(out[n].describe().loc[["mean", "max"]].round(1).to_string(), "\nareas with any", (out[n].sum(axis=1) > 0).sum())


if __name__ == "__main__":
    main()
