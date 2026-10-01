#!/usr/bin/env python3
"""Create official Seoul commercial-area candidates inside the transit life area.

The unit of analysis is an official Seoul commercial-area polygon (골목상권,
발달상권, 전통시장, 관광특구), rather than a manually named neighbourhood.
An area is accessible when a stop reached within 30 minutes is within a walking
buffer of its polygon.  This deliberately keeps access a continuous feature
instead of inheriting the score of its parent administrative dong.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd


PERIODS = (8, 14, 19)
AREA_COLUMNS = {
    "TRDAR_SE_C": "area_type_code",
    "TRDAR_SE_1": "area_type_name",
    "TRDAR_CD": "area_code",
    "TRDAR_CD_N": "area_name",
    "ADSTRD_CD": "source_admin_code",
    "ADSTRD_CD_": "source_admin_name",
}


def normalize_area_code(value: object) -> str:
    """Keep Seoul commercial-area IDs as a seven digit string."""
    digits = "".join(char for char in str(value).split(".")[0] if char.isdigit())
    return digits.zfill(7)


def normalize_admin_code(value: object) -> str:
    digits = "".join(char for char in str(value).split(".")[0] if char.isdigit())
    if len(digits) >= 10:
        digits = digits[:8]
    return digits.zfill(8)


def purpose_group(service_name: object) -> str:
    """Map Seoul's service-industry labels to the project's six purpose labels."""
    name = str(service_name)
    if name == "커피-음료":
        return "카페"
    if any(word in name for word in ["음식점", "분식", "치킨", "패스트푸드", "제과점", "반찬"]):
        return "식사"
    if any(word in name for word in ["서적", "문구", "독서", "교습학원", "외국어학원", "예술학원"]):
        return "공부"
    if any(word in name for word in ["의류", "가방", "신발", "화장품", "귀금속", "슈퍼마켓", "편의점", "판매", "가구", "가전", "안경", "완구", "화초", "용품", "청과", "미곡", "수산", "육류"]):
        return "쇼핑"
    if any(word in name for word in ["노래방", "PC방", "당구장", "골프", "스포츠", "클럽", "주점", "여관"]):
        return "여가문화"
    return "생활서비스"


def access_tier(minimum_ratio: float) -> str:
    """Name the stable access tier from the worst of the three time periods."""
    if minimum_ratio >= 0.80:
        return "core_80pct_all_periods"
    if minimum_ratio >= 0.50:
        return "base_50pct_all_periods"
    if minimum_ratio >= 0.25:
        return "exploration_25pct_all_periods"
    return "excluded_below_25pct"


def read_zip_csv(path: Path, encoding: str = "cp949") -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"Expected one CSV in {path}, found {members}")
        with archive.open(members[0]) as source:
            return pd.read_csv(source, encoding=encoding, low_memory=False)


def load_areas(path: Path) -> gpd.GeoDataFrame:
    areas = gpd.read_file(f"zip://{path}").rename(columns=AREA_COLUMNS)
    missing = set(AREA_COLUMNS.values()) - set(areas.columns)
    if missing:
        raise ValueError(f"Commercial area geometry has missing columns: {sorted(missing)}")
    areas = areas[list(AREA_COLUMNS.values()) + ["geometry"]].copy()
    areas["area_code"] = areas["area_code"].map(normalize_area_code)
    areas["source_admin_code"] = areas["source_admin_code"].map(normalize_admin_code)
    return areas.to_crs(5181).reset_index(drop=True)


def prepare_dong_boundaries(dongs: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Keep the official administrative code distinct from the spatial-data code."""
    required = {"emd8", "emdcd", "emdnm", "sggnm", "geometry"}
    missing = required - set(dongs.columns)
    if missing:
        raise ValueError(f"Administrative boundaries have missing columns: {sorted(missing)}")
    out = dongs.rename(columns={
        "emd8": "spatial_admin_code",
        "emdcd": "admin_code",
        "emdnm": "admin_name",
        "sggnm": "district_name",
    })[["spatial_admin_code", "admin_code", "admin_name", "district_name", "geometry"]].copy()
    out["spatial_admin_code"] = out["spatial_admin_code"].map(normalize_admin_code)
    out["admin_code"] = out["admin_code"].map(normalize_admin_code)
    return out


def build_area_dong_overlap(areas: gpd.GeoDataFrame, dongs: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return every area/dong intersection and its polygon-area share."""
    left = areas[["area_code", "area_name", "area_type_name", "geometry"]]
    right = dongs[["admin_code", "admin_name", "district_name", "geometry"]]
    intersected = gpd.overlay(left, right, how="intersection", keep_geom_type=False)
    intersected["overlap_m2"] = intersected.geometry.area
    area_m2 = areas.set_index("area_code").geometry.area.rename("area_m2")
    out = pd.DataFrame(intersected.drop(columns="geometry"))
    out["area_m2"] = out["area_code"].map(area_m2)
    out["overlap_share"] = out["overlap_m2"] / out["area_m2"]
    return out.sort_values(["area_code", "overlap_share"], ascending=[True, False]).reset_index(drop=True)


def area_access_by_period(
    reachable_path: Path,
    candidate_areas: gpd.GeoDataFrame,
    buffer_m: float,
    total_origins: int,
) -> pd.DataFrame:
    """Calculate area access as unique origins with a reached stop near an area."""
    reachable = pd.read_csv(reachable_path, dtype={"origin_id": str, "stop_id": str})
    stop_points = reachable[["origin_id", "stop_id", "longitude", "latitude"]].dropna().drop_duplicates()
    points = gpd.GeoDataFrame(
        stop_points,
        geometry=gpd.points_from_xy(stop_points.longitude, stop_points.latitude),
        crs=4326,
    ).to_crs(5181)
    buffered = candidate_areas[["area_code", "geometry"]].copy()
    buffered["geometry"] = buffered.geometry.buffer(buffer_m)
    joined = gpd.sjoin(points, buffered, how="inner", predicate="within")
    counts = joined.groupby("area_code", as_index=False)["origin_id"].nunique().rename(columns={"origin_id": "reachable_origin_count"})
    counts["reachable_origin_ratio"] = counts["reachable_origin_count"] / total_origins
    return counts


def build_commercial_features(store_path: Path, sales_path: Path) -> pd.DataFrame:
    """Aggregate the 2025 official point-of-sale/sales data by area and purpose."""
    stores = read_zip_csv(store_path)
    stores["area_code"] = stores["trdar_cd"].map(normalize_area_code)
    stores["purpose"] = stores["svc_induty_cd_nm"].map(purpose_group)
    store_wide = stores.groupby(["area_code", "purpose"], as_index=False)["stor_co"].sum().pivot(
        index="area_code", columns="purpose", values="stor_co"
    ).fillna(0).add_prefix("store_").reset_index()
    store_total = stores.groupby("area_code", as_index=False)["stor_co"].sum().rename(columns={"stor_co": "store_count_total"})

    sales = read_zip_csv(sales_path)
    sales["area_code"] = sales["상권_코드"].map(normalize_area_code)
    sales["purpose"] = sales["서비스_업종_코드_명"].map(purpose_group)
    sales = sales.rename(columns={"당월_매출_금액": "sales_amount", "당월_매출_건수": "sales_count"})
    sale_wide = sales.groupby(["area_code", "purpose"], as_index=False)[["sales_amount", "sales_count"]].sum()
    amount = sale_wide.pivot(index="area_code", columns="purpose", values="sales_amount").fillna(0).add_prefix("sales_amount_")
    count = sale_wide.pivot(index="area_code", columns="purpose", values="sales_count").fillna(0).add_prefix("sales_count_")
    sales_total = sales.groupby("area_code", as_index=False)[["sales_amount", "sales_count"]].sum().rename(
        columns={"sales_amount": "sales_amount_total", "sales_count": "sales_count_total"}
    )
    return store_total.merge(store_wide, on="area_code", how="outer").merge(
        sales_total.merge(amount.join(count), on="area_code", how="left"), on="area_code", how="outer"
    ).fillna(0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--areas", type=Path, default=Path("data/raw/commercial_area/commercial_area.zip"))
    parser.add_argument("--stores", type=Path, default=Path("data/raw/commercial_area/commercial_store_2025.zip"))
    parser.add_argument("--sales", type=Path, default=Path("data/raw/commercial_area/commercial_sales_2025.zip"))
    parser.add_argument("--dongs", type=Path, default=Path("data/external/seoul_administrative_dongs_20260701.geojson"))
    parser.add_argument("--candidates", type=Path, default=Path("data/processed/local_transit_30min/time_period_candidates.csv"))
    parser.add_argument("--transit-root", type=Path, default=Path("data/processed/local_transit_30min"))
    parser.add_argument("--origins", type=Path, default=Path("data/external/odsay_origins.csv"))
    parser.add_argument("--buffer-m", type=float, default=400)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/commercial_area_accessibility"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    areas = load_areas(args.areas)
    dongs = prepare_dong_boundaries(gpd.read_file(args.dongs).to_crs(5181))
    overlap = build_area_dong_overlap(areas, dongs)
    overlap.to_csv(args.output_dir / "commercial_area_dong_overlap.csv", index=False, encoding="utf-8-sig")

    # Evaluate every official polygon directly against reached stop coordinates.
    # Administrative dongs are descriptive metadata, not a pre-filter: using a
    # different code family here previously discarded valid areas such as Hoegi.
    candidate_areas = areas.copy()
    primary = overlap.sort_values("overlap_share", ascending=False).drop_duplicates("area_code").rename(columns={
        "admin_code": "primary_admin_code", "admin_name": "primary_admin_name", "district_name": "primary_district_name",
        "overlap_share": "primary_admin_overlap_share",
    })[["area_code", "primary_admin_code", "primary_admin_name", "primary_district_name", "primary_admin_overlap_share"]]
    summary = candidate_areas.drop(columns="geometry").merge(primary, on="area_code", how="left")
    total_origins = pd.read_csv(args.origins, dtype={"origin_id": str}).origin_id.nunique()
    for hour in PERIODS:
        counts = area_access_by_period(args.transit_root / f"h{hour:02d}" / "reachable_stops_by_origin.csv", candidate_areas, args.buffer_m, total_origins)
        summary = summary.merge(counts[["area_code", "reachable_origin_ratio"]].rename(columns={"reachable_origin_ratio": f"ratio_{hour:02d}"}), on="area_code", how="left")
    ratio_cols = [f"ratio_{hour:02d}" for hour in PERIODS]
    summary[ratio_cols] = summary[ratio_cols].fillna(0)
    summary["minimum_period_ratio"] = summary[ratio_cols].min(axis=1)
    summary["mean_period_ratio"] = summary[ratio_cols].mean(axis=1)
    summary["access_tier"] = summary.minimum_period_ratio.map(access_tier)
    summary["access_buffer_m"] = args.buffer_m
    features = build_commercial_features(args.stores, args.sales)
    summary = summary.merge(features, on="area_code", how="left").fillna(0)
    summary = summary.sort_values(["minimum_period_ratio", "sales_amount_total"], ascending=[False, False]).reset_index(drop=True)
    summary.to_csv(args.output_dir / "commercial_area_accessibility_summary.csv", index=False, encoding="utf-8-sig")
    candidates = summary[summary.minimum_period_ratio >= 0.25].copy()
    candidates.to_csv(args.output_dir / "commercial_area_candidates_25pct.csv", index=False, encoding="utf-8-sig")
    candidate_areas.merge(candidates[["area_code", "minimum_period_ratio", "mean_period_ratio", "access_tier"]], on="area_code", how="inner").to_crs(4326).to_file(args.output_dir / "commercial_area_candidates_25pct.geojson", driver="GeoJSON")
    report = f"""# 공식 상권 단위 접근성 결과\n\n- 공간 단위: 서울시 상권분석서비스의 공식 상권 폴리곤 {len(areas):,}개\n- 계산 방식: 행정동 코드 사전 필터 없이 공식 상권 전체를 도달 정류장과 직접 공간 결합\n- 접근 판정: 30분 내 도달한 정류장이 상권 폴리곤 경계로부터 {args.buffer_m:.0f}m 이내인 출발지의 비율\n- 출발지: {total_origins}개(동대문구 버스정류장·지하철역)\n- 접근성 평가 공식 상권: {len(candidate_areas):,}개\n- 상권 자체 접근성 25% 이상(모든 시간대): {len(candidates):,}개\n- 50% 이상: {(summary.minimum_period_ratio >= 0.5).sum():,}개\n- 80% 이상: {(summary.minimum_period_ratio >= 0.8).sum():,}개\n\n`primary_admin_*`은 상권 폴리곤 면적이 가장 많이 겹치는 행정동일 뿐입니다. `admin_code`는 서울시 상권 통계와 결합 가능한 공식 코드이고, 원 공간자료의 `emd8`은 `spatial_admin_code`로 별도 보존합니다.\n"""
    (args.output_dir / "COMMERCIAL_AREA_ACCESSIBILITY_REPORT.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
