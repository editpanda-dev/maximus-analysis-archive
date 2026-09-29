#!/usr/bin/env python3
"""Map current nightlife POIs to official-area interiors without scoring adult venues."""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


VALID_CLASSES = {"night_food", "adult_nightlife"}


def scope_nightlife_pois(places: pd.DataFrame, areas: gpd.GeoDataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {"place_id", "venue_class", "longitude", "latitude"}
    missing = sorted(required - set(places.columns))
    if missing:
        raise ValueError(f"places missing columns: {', '.join(missing)}")
    if places.place_id.astype(str).duplicated().any():
        raise ValueError("places has duplicate place_id")
    if not set(places.venue_class).issubset(VALID_CLASSES):
        raise ValueError("unknown venue_class")
    area = areas[["area_code", "area_name", "geometry"]].copy().to_crs("EPSG:4326")
    area["area_code"] = area.area_code.astype(str)
    points = gpd.GeoDataFrame(
        places.copy(), geometry=gpd.points_from_xy(places.longitude, places.latitude), crs="EPSG:4326"
    )
    matches = []
    for row in points.itertuples():
        hit = area[area.geometry.covers(row.geometry)]
        if hit.empty:
            matches.append((None, None, "OUTSIDE_SELECTED_AREA"))
        else:
            first = hit.iloc[0]
            matches.append((str(first.area_code), first.area_name, "INSIDE_OFFICIAL_AREA"))
    detail = places.copy()
    detail[["area_code", "area_name", "scope_status"]] = pd.DataFrame(matches, index=detail.index)
    inside = detail[detail.scope_status.eq("INSIDE_OFFICIAL_AREA")]
    counts = inside.pivot_table(index="area_code", columns="venue_class", values="place_id", aggfunc="nunique", fill_value=0)
    counts = counts.rename(columns={"night_food": "night_food_inside_count", "adult_nightlife": "adult_nightlife_inside_count"})
    features = area[["area_code", "area_name"]].drop_duplicates().merge(counts, on="area_code", how="left").fillna(0)
    for column in ["night_food_inside_count", "adult_nightlife_inside_count"]:
        if column not in features:
            features[column] = 0
        features[column] = features[column].astype(int)
    return detail, features


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--places", required=True)
    parser.add_argument("--areas", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    parser.add_argument("--output-dir", default="data/processed/nightlife_poi_v1")
    args = parser.parse_args()
    detail, features = scope_nightlife_pois(pd.read_csv(args.places, dtype={"place_id": str}), gpd.read_file(args.areas))
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output / "nightlife_poi_scope_detail.csv", index=False, encoding="utf-8-sig")
    features.to_csv(output / "official_area_nightlife_poi_features_786.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
