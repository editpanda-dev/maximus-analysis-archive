#!/usr/bin/env python3
"""Build a current study-stay ranking from historic commercial data and current POIs."""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


STUDY = "공부"
CAFE = "카페"
PLACE_TYPES = ("study_cafe", "starbucks")


def _percentile(values: pd.Series) -> pd.Series:
    values = values.fillna(0.0)
    if values.nunique(dropna=False) <= 1:
        return pd.Series(50.0, index=values.index)
    return values.rank(method="average", pct=True) * 100


def _positive_percentile(values: pd.Series) -> pd.Series:
    """Rank positive availability signals while keeping a true zero at zero."""
    values = values.fillna(0.0)
    result = pd.Series(0.0, index=values.index)
    positive = values.gt(0)
    if positive.any():
        result.loc[positive] = values.loc[positive].rank(method="average", pct=True) * 100
    return result


def map_pois_to_areas(areas: gpd.GeoDataFrame, pois: pd.DataFrame) -> pd.DataFrame:
    """Count current study-stay POIs within each official commercial-area polygon."""
    required = {"place_id", "place_type", "longitude", "latitude"}
    missing = required - set(pois.columns)
    if missing:
        raise ValueError(f"POI columns missing: {sorted(missing)}")

    area_frame = areas[["area_code", "geometry"]].copy()
    area_frame["area_code"] = area_frame["area_code"].astype(str)
    area_sizes = area_frame.to_crs("EPSG:5179")
    area_sizes = pd.DataFrame({
        "area_code": area_sizes["area_code"],
        "area_km2": area_sizes.geometry.area / 1_000_000,
    })
    poi_frame = pois.drop_duplicates("place_id").copy()
    poi_frame = poi_frame[poi_frame["place_type"].isin(PLACE_TYPES)]
    point_frame = gpd.GeoDataFrame(
        poi_frame,
        geometry=gpd.points_from_xy(poi_frame.longitude, poi_frame.latitude),
        crs="EPSG:4326",
    ).to_crs(area_frame.crs)
    joined = gpd.sjoin(point_frame, area_frame, how="inner", predicate="within")
    counts = (
        joined.groupby(["area_code", "place_type"])["place_id"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(columns=PLACE_TYPES, fill_value=0)
        .rename(columns={
            "study_cafe": "study_cafe_inside_count",
            "starbucks": "starbucks_inside_count",
        })
        .reset_index()
    )
    result = area_sizes.merge(counts, on="area_code", how="left", validate="one_to_one")
    return result.fillna(0).sort_values("area_code").reset_index(drop=True)


def build_study_stay_enrichment(
    rankings: pd.DataFrame,
    poi_features: pd.DataFrame,
    public_features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Combine study rooms, cafe supply, public facilities, and current POIs."""
    rankings = rankings.copy()
    rankings["area_code"] = rankings["area_code"].astype(str)
    study = rankings[rankings["purpose"] == STUDY][
        ["area_code", "purpose_store_count", "minimum_period_ratio"]
    ].rename(columns={"purpose_store_count": "study_room_store_count"})
    cafes = rankings[rankings["purpose"] == CAFE][["area_code", "purpose_store_count"]].rename(
        columns={"purpose_store_count": "cafe_store_count_2025"}
    )
    out = study.merge(cafes, on="area_code", how="inner", validate="one_to_one")
    out = out.merge(poi_features, on="area_code", how="left", validate="one_to_one")
    required_public = {
        "area_code",
        "study_public_inside_count",
        "study_public_nearby_only_count",
        "poi_public_library_inside_count",
        "poi_reading_room_inside_count",
        "poi_university_learning_facility_inside_count",
        "poi_youth_space_inside_count",
    }
    if public_features is None:
        public_features = pd.DataFrame({"area_code": out["area_code"]})
        for column in required_public.difference({"area_code"}):
            public_features[column] = 0
    missing_public = required_public.difference(public_features.columns)
    if missing_public:
        raise ValueError(f"Public facility columns missing: {sorted(missing_public)}")
    public_columns = sorted(required_public.difference({"area_code"}))
    public = public_features[["area_code", *public_columns]].copy()
    public["area_code"] = public["area_code"].astype(str)
    out = out.merge(public, on="area_code", how="left", validate="one_to_one")
    for column in ("study_cafe_inside_count", "starbucks_inside_count"):
        out[column] = out[column].fillna(0.0)
    for column in public_columns:
        out[column] = out[column].fillna(0.0)
    if (out["area_km2"] <= 0).any():
        raise ValueError("Every commercial-area polygon must have a positive area")

    out["study_room_per_km2"] = out["study_room_store_count"] / out["area_km2"]
    out["cafe_store_per_km2_2025"] = out["cafe_store_count_2025"] / out["area_km2"]
    out["study_cafe_per_km2"] = out["study_cafe_inside_count"] / out["area_km2"]
    out["starbucks_per_km2"] = out["starbucks_inside_count"] / out["area_km2"]
    out["study_public_inside_per_km2"] = out["study_public_inside_count"] / out["area_km2"]
    out["study_public_nearby_only_per_km2"] = (
        out["study_public_nearby_only_count"] / out["area_km2"]
    )

    out["study_room_percentile"] = _percentile(np.log1p(out["study_room_per_km2"]))
    out["cafe_supply_percentile"] = _percentile(np.log1p(out["cafe_store_per_km2_2025"]))
    out["study_cafe_percentile"] = _percentile(np.log1p(out["study_cafe_per_km2"]))
    out["starbucks_percentile"] = _percentile(np.log1p(out["starbucks_per_km2"]))
    out["study_public_inside_percentile"] = _positive_percentile(
        np.log1p(out["study_public_inside_per_km2"])
    )
    out["study_public_nearby_only_percentile"] = _positive_percentile(
        np.log1p(out["study_public_nearby_only_per_km2"])
    )
    out["study_public_percentile"] = (
        0.8 * out["study_public_inside_percentile"]
        + 0.2 * out["study_public_nearby_only_percentile"]
    )
    out["access_percentile"] = _percentile(out["minimum_period_ratio"])
    out["study_stay_current_score"] = (
        0.15 * out["study_room_percentile"]
        + 0.15 * out["cafe_supply_percentile"]
        + 0.30 * out["study_cafe_percentile"]
        + 0.10 * out["starbucks_percentile"]
        + 0.20 * out["study_public_percentile"]
        + 0.10 * out["access_percentile"]
    )
    out = out.sort_values(
        ["study_stay_current_score", "area_code"], ascending=[False, True]
    ).reset_index(drop=True)
    out["study_stay_current_rank"] = np.arange(1, len(out) + 1)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--areas",
        default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson",
    )
    parser.add_argument("--pois", required=True, help="Kakao study_cafe/starbucks POI CSV")
    parser.add_argument(
        "--rankings",
        default="data/processed/commercial_area_purpose_features/official_area_purpose_latest_rankings.csv",
    )
    parser.add_argument(
        "--public-features",
        default="data/processed/study_public_facility_features.csv",
        help="Public-library, reading-room, youth-space, and university-learning features",
    )
    parser.add_argument("--output-dir", default="data/processed/study_stay_poi_enrichment")
    parser.add_argument("--snapshot-date", required=True)
    args = parser.parse_args()

    areas = gpd.read_file(args.areas)
    poi = pd.read_csv(args.pois, dtype={"place_id": str})
    rankings = pd.read_csv(args.rankings, dtype={"area_code": str})
    public_features = pd.read_csv(args.public_features, dtype={"area_code": str})
    public_snapshot_dates = public_features["feature_snapshot_date"].dropna().unique()
    if len(public_snapshot_dates) != 1:
        raise ValueError("Public facility features must contain one feature_snapshot_date")
    features = map_pois_to_areas(areas, poi)
    result = build_study_stay_enrichment(rankings, features, public_features)
    result["poi_snapshot_date"] = args.snapshot_date
    result["public_facility_snapshot_date"] = public_snapshot_dates[0]
    result["historical_2025_use_allowed"] = False
    result["poi_source"] = "Kakao Local keyword search"

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_dir / "official_area_study_stay_poi_features_current.csv", index=False, encoding="utf-8-sig")
    result.to_csv(output_dir / "official_area_study_stay_enriched_current.csv", index=False, encoding="utf-8-sig")
    report = f"""# 공부 체류 POI 보조순위\n\n- 대상: 공식 상권 {len(result):,}개\n- 2025년 신호: 독서실 점포 수 15% + 카페 점포 수 15%\n- 현재 POI 신호: 스터디카페 수 30% + 스타벅스 수 10% + 공공 학습시설 수 20%\n- 접근성: 세 시간대 최소 접근률 10%\n- POI 기준일: {args.snapshot_date}\n\n공공 학습시설 점수는 상권 내부 시설 밀도 80%와 상권 밖 400m 이내 시설 밀도 20%로 계산한다. 대상은 공공도서관·열람실·청년공간·대학 학습시설뿐이며, 스터디카페·대형카페는 카카오 장소 피처와 중복되지 않도록 공공시설 점수에서 제외한다.\n\n## 사용 제한\n\n스터디카페와 스타벅스, 공공 학습시설은 현재 스냅샷이다. 따라서 이 순위는 현재 추천 후보를 보강하기 위한 것이며, 2025년 매출 예측·검증에는 사용하지 않는다. 스타벅스는 대형·좌석형 카페의 제한적 프록시이므로, 향후 장소 상세정보·리뷰·혼잡도 검증으로 확장한다.\n"""
    (output_dir / "README.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
