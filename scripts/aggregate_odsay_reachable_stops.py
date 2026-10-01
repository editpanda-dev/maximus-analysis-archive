#!/usr/bin/env python3
"""List bus stops contained by each cached ODsay isochrone."""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--isochrones", type=Path, required=True)
    parser.add_argument("--stops", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/odsay_30min"))
    args = parser.parse_args()

    iso = gpd.read_file(args.isochrones).set_crs(4326, allow_override=True)
    stops = pd.read_csv(args.stops, encoding="utf-8-sig")
    points = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["longitude"], stops["latitude"]),
        crs=4326,
    )
    joined = gpd.sjoin(
        points,
        iso[["origin_id", "origin_name", "geometry"]],
        how="inner",
        predicate="within",
    ).drop(columns=["geometry", "index_right"])
    joined = joined.sort_values(["origin_id", "stop_id"])
    summary = (
        joined.groupby(["stop_id", "stop_name", "longitude", "latitude", "stop_type"], as_index=False)
        .agg(reachable_origin_count=("origin_id", "nunique"))
    )
    total_origins = iso["origin_id"].nunique()
    summary["total_origin_count"] = total_origins
    summary["reachable_origin_ratio"] = summary["reachable_origin_count"] / total_origins
    summary = summary.sort_values(["reachable_origin_ratio", "stop_name"], ascending=[False, True])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    joined.to_csv(args.output_dir / "reachable_bus_stops_by_origin.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(args.output_dir / "reachable_bus_stops_summary.csv", index=False, encoding="utf-8-sig")
    print(f"saved {len(joined)} origin-stop pairs and {len(summary)} unique reachable bus stops")


if __name__ == "__main__":
    main()
