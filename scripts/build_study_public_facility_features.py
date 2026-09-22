"""Map public study-stay facilities to the 786 reachable commercial areas.

The input is a versioned POI snapshot. It deliberately keeps facility types
separate so downstream scoring can include public facilities without double
counting commercial study cafés or large cafés maintained elsewhere.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


PUBLIC_TYPES = {
    "public_library",
    "reading_room",
    "youth_space",
    "university_learning_facility",
}


def count_by_area(links: pd.DataFrame, areas: pd.DataFrame, suffix: str) -> pd.DataFrame:
    """Return total and facility-type counts for one point-to-area relation."""
    result = links.groupby("area_code")["place_id"].nunique().rename(f"study_public_{suffix}_count")
    result = result.to_frame()
    for facility_type in sorted(PUBLIC_TYPES):
        col = f"poi_{facility_type}_{suffix}_count"
        values = (
            links.loc[links["facility_type"].eq(facility_type)]
            .groupby("area_code")["place_id"]
            .nunique()
            .rename(col)
        )
        result = result.join(values, how="outer")
    return areas[["area_code"]].merge(result.reset_index(), on="area_code", how="left").fillna(0)


def build_features(pois_path: Path, areas_path: Path, output_path: Path, buffer_m: int) -> pd.DataFrame:
    pois = pd.read_csv(pois_path, dtype={"place_id": "string"})
    required = {
        "place_id",
        "facility_type",
        "longitude",
        "latitude",
        "aggregation_eligible",
        "public_access_verified",
        "snapshot_date",
    }
    missing = required.difference(pois.columns)
    if missing:
        raise ValueError(f"POI input is missing columns: {sorted(missing)}")

    eligible_public = pois["aggregation_eligible"].eq(1) & pois["facility_type"].isin(PUBLIC_TYPES)
    university_access_ok = ~pois["facility_type"].eq("university_learning_facility") | pois[
        "public_access_verified"
    ].eq(1)
    all_public_pois = pois.loc[eligible_public].copy()
    scored_public_pois = all_public_pois.loc[university_access_ok].copy()
    snapshot_dates = all_public_pois["snapshot_date"].dropna().unique()
    if len(snapshot_dates) != 1:
        raise ValueError("Eligible public facility POIs must contain one snapshot_date")
    all_points = gpd.GeoDataFrame(
        all_public_pois,
        geometry=gpd.points_from_xy(all_public_pois["longitude"], all_public_pois["latitude"]),
        crs="EPSG:4326",
    ).to_crs("EPSG:5186")
    scored_points = all_points.loc[all_points["place_id"].isin(scored_public_pois["place_id"])].copy()
    areas = gpd.read_file(areas_path).to_crs("EPSG:5186")
    area_fields = ["area_code", "area_name", "area_type_name", "minimum_period_ratio", "mean_period_ratio", "access_tier", "geometry"]
    areas = areas[area_fields].copy()

    scored_inside = gpd.sjoin(scored_points, areas[["area_code", "geometry"]], how="inner", predicate="within")
    scored_inside = scored_inside[["place_id", "facility_type", "area_code"]]
    all_inside = gpd.sjoin(all_points, areas[["area_code", "geometry"]], how="inner", predicate="within")
    all_inside = all_inside[["place_id", "facility_type", "area_code"]]
    buffered_areas = areas[["area_code", "geometry"]].copy()
    buffered_areas["geometry"] = buffered_areas.geometry.buffer(buffer_m)
    scored_buffered = gpd.sjoin(scored_points, buffered_areas, how="inner", predicate="intersects")
    scored_buffered = scored_buffered[["place_id", "facility_type", "area_code"]]
    all_buffered = gpd.sjoin(all_points, buffered_areas, how="inner", predicate="intersects")
    all_buffered = all_buffered[["place_id", "facility_type", "area_code"]]

    features = pd.DataFrame(areas.drop(columns="geometry"))
    scored_inside_counts = count_by_area(scored_inside, features, "inside")[["area_code", "study_public_inside_count"]]
    scored_buffer_counts = count_by_area(scored_buffered, features, f"buffer{buffer_m}")[["area_code", f"study_public_buffer{buffer_m}_count"]]
    all_inside_counts = count_by_area(all_inside, features, "inside").rename(
        columns={"study_public_inside_count": "study_public_all_inside_count"}
    )
    all_buffer_counts = count_by_area(all_buffered, features, f"buffer{buffer_m}").rename(
        columns={f"study_public_buffer{buffer_m}_count": f"study_public_all_buffer{buffer_m}_count"}
    )
    features = features.merge(scored_inside_counts, on="area_code", how="left")
    features = features.merge(all_inside_counts, on="area_code", how="left")
    features = features.merge(scored_buffer_counts, on="area_code", how="left")
    # Type-specific columns come from the full candidate universe so that
    # unverified university candidates remain auditable without entering the
    # production public-facility score.
    features = features.merge(all_buffer_counts, on="area_code", how="left")
    count_columns = [c for c in features.columns if c.endswith("_count")]
    features[count_columns] = features[count_columns].fillna(0).astype(int)
    features["study_public_nearby_only_count"] = (
        features[f"study_public_buffer{buffer_m}_count"] - features["study_public_inside_count"]
    )
    features["study_public_all_nearby_only_count"] = (
        features[f"study_public_all_buffer{buffer_m}_count"] - features["study_public_all_inside_count"]
    )
    features["feature_snapshot_date"] = snapshot_dates[0]
    features["reachability_rule"] = "Dongdaemun origins; public transit <=30min; all 08/14/19 ratios >=25%"
    features["source_scope"] = "public_library, reading_room, youth_space"
    features["source_scope_all"] = "public_library, reading_room, youth_space, university_learning_facility"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.sort_values("area_code").to_csv(output_path, index=False)
    return features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pois", type=Path, required=True)
    parser.add_argument("--areas", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/study_public_facility_features.csv"))
    parser.add_argument("--buffer-m", type=int, default=400)
    args = parser.parse_args()
    features = build_features(args.pois, args.areas, args.output, args.buffer_m)
    print(f"Wrote {len(features):,} area rows to {args.output}")


if __name__ == "__main__":
    main()
