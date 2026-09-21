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
    pois = pois.loc[eligible_public & university_access_ok].copy()
    snapshot_dates = pois["snapshot_date"].dropna().unique()
    if len(snapshot_dates) != 1:
        raise ValueError("Eligible public facility POIs must contain one snapshot_date")
    points = gpd.GeoDataFrame(
        pois,
        geometry=gpd.points_from_xy(pois["longitude"], pois["latitude"]),
        crs="EPSG:4326",
    ).to_crs("EPSG:5186")
    areas = gpd.read_file(areas_path).to_crs("EPSG:5186")
    area_fields = ["area_code", "area_name", "area_type_name", "minimum_period_ratio", "mean_period_ratio", "access_tier", "geometry"]
    areas = areas[area_fields].copy()

    inside = gpd.sjoin(points, areas[["area_code", "geometry"]], how="inner", predicate="within")
    inside = inside[["place_id", "facility_type", "area_code"]]
    buffered_areas = areas[["area_code", "geometry"]].copy()
    buffered_areas["geometry"] = buffered_areas.geometry.buffer(buffer_m)
    buffered = gpd.sjoin(points, buffered_areas, how="inner", predicate="intersects")
    buffered = buffered[["place_id", "facility_type", "area_code"]]

    features = pd.DataFrame(areas.drop(columns="geometry"))
    features = features.merge(count_by_area(inside, features, "inside"), on="area_code", how="left")
    features = features.merge(count_by_area(buffered, features, f"buffer{buffer_m}"), on="area_code", how="left")
    count_columns = [c for c in features.columns if c.endswith("_count")]
    features[count_columns] = features[count_columns].fillna(0).astype(int)
    features["study_public_nearby_only_count"] = (
        features[f"study_public_buffer{buffer_m}_count"] - features["study_public_inside_count"]
    )
    features["feature_snapshot_date"] = snapshot_dates[0]
    features["reachability_rule"] = "Dongdaemun origins; public transit <=30min; all 08/14/19 ratios >=25%"
    features["source_scope"] = (
        "public_library, reading_room, youth_space, "
        "university_learning_facility(public_access_verified=1)"
    )
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
