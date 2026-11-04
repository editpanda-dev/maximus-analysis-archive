#!/usr/bin/env python3
"""Replace Euclidean legacy proximity with cached Kakao walking-route results.

The origin is the nearest point on the selected official-area boundary.  This
is a transparent boundary proxy, not a verified shop entrance: failures and
unknown routes remain explicit in the output.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.ops import nearest_points


KAKAO_WALK_URL = "https://dapi.kakao.com/v2/routing/walk"


def fetch_walk_route(
    session: requests.Session,
    api_key: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    timeout: int = 30,
) -> dict[str, float | str]:
    """Query one Kakao shortest walking route without hiding failed statuses."""
    response = session.get(
        KAKAO_WALK_URL,
        headers={"Authorization": f"KakaoAK {api_key}"},
        params={
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "route_mode": "SHORTEST",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    status = str(payload.get("status", "UNKNOWN_RESPONSE"))
    if status == "SAME_POINT":
        return {"route_status": status, "walk_distance_m": 0.0, "walk_time_s": 0.0}
    if status != "OK":
        return {"route_status": status, "walk_distance_m": np.nan, "walk_time_s": np.nan}
    properties = payload.get("route", {}).get("properties", {})
    if "totalDistance" not in properties or "totalTime" not in properties:
        return {"route_status": "MALFORMED_OK_RESPONSE", "walk_distance_m": np.nan, "walk_time_s": np.nan}
    return {
        "route_status": "OK",
        "walk_distance_m": float(properties["totalDistance"]),
        "walk_time_s": float(properties["totalTime"]),
    }


def add_boundary_origins(queue: pd.DataFrame, areas: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add the nearest point on each selected area polygon boundary as origin."""
    required = {"place_id", "nearest_area_code", "longitude", "latitude", "inside_official_area"}
    missing = sorted(required - set(queue.columns))
    if missing:
        raise ValueError(f"queue missing columns: {', '.join(missing)}")
    area_frame = areas[["area_code", "geometry"]].copy()
    area_frame["area_code"] = area_frame["area_code"].astype(str)
    area_metric = area_frame.to_crs("EPSG:5186").set_index("area_code")
    points = gpd.GeoDataFrame(
        queue.copy(),
        geometry=gpd.points_from_xy(queue.longitude, queue.latitude),
        crs="EPSG:4326",
    ).to_crs("EPSG:5186")

    origin_geometries = []
    for row in points.itertuples():
        boundary = area_metric.loc[str(row.nearest_area_code), "geometry"].boundary
        origin_geometries.append(nearest_points(row.geometry, boundary)[1])
    origins = gpd.GeoSeries(origin_geometries, crs="EPSG:5186").to_crs("EPSG:4326")
    points["boundary_origin_x"] = origins.x.to_numpy()
    points["boundary_origin_y"] = origins.y.to_numpy()
    return points.to_crs("EPSG:4326")


def build_walk_access(
    queue: pd.DataFrame,
    areas: gpd.GeoDataFrame,
    api_key: str,
    max_new_calls: int = 900,
    sleep_seconds: float = 0.15,
    timeout: int = 30,
    existing_cache: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute only external POI routes; inside facilities are distance zero."""
    out = add_boundary_origins(queue, areas)
    out["place_id"] = out["place_id"].astype(str)
    out["nearest_area_code"] = out["nearest_area_code"].astype(str)
    key_columns = ["place_id", "nearest_area_code"]
    cache: dict[tuple[str, str], dict[str, object]] = {}
    if existing_cache is not None and not existing_cache.empty:
        for row in existing_cache.itertuples():
            cache[(str(row.place_id), str(row.nearest_area_code))] = {
                "route_status": row.route_status,
                "walk_distance_m": row.walk_distance_m,
                "walk_time_s": row.walk_time_s,
            }

    results: list[dict[str, object]] = []
    calls = 0
    session = requests.Session()
    for row in out.itertuples():
        key = (str(row.place_id), str(row.nearest_area_code))
        if bool(row.inside_official_area):
            route = {"route_status": "INSIDE_OFFICIAL_AREA", "walk_distance_m": 0.0, "walk_time_s": 0.0}
        elif key in cache:
            route = cache[key]
        elif calls >= max_new_calls:
            route = {"route_status": "PENDING_DAILY_QUOTA", "walk_distance_m": np.nan, "walk_time_s": np.nan}
        else:
            try:
                route = fetch_walk_route(
                    session, api_key,
                    float(row.boundary_origin_x), float(row.boundary_origin_y),
                    float(row.longitude), float(row.latitude), timeout=timeout,
                )
            except requests.RequestException as error:
                route = {"route_status": f"REQUEST_ERROR:{type(error).__name__}", "walk_distance_m": np.nan, "walk_time_s": np.nan}
            calls += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
        results.append({**row._asdict(), **route})

    result = pd.DataFrame(results).drop(columns=["geometry"], errors="ignore")
    same_point = result["route_status"].eq("SAME_POINT")
    result.loc[same_point, ["walk_distance_m", "walk_time_s"]] = 0.0
    result["walk_access_400"] = result["walk_distance_m"].le(400)
    result["walk_access_500"] = result["walk_distance_m"].le(500)
    result["walk_access_600"] = result["walk_distance_m"].le(600)
    result["route_origin_definition"] = "nearest_selected_area_boundary_proxy"
    result["route_provider"] = "Kakao Map Walking Routes REST API"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queue",
        default="data/processed/cafe_study_v1/c_stay_s4_review_queue_786_euclidean_legacy.csv",
    )
    parser.add_argument(
        "--areas",
        default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson",
    )
    parser.add_argument("--output", default="data/processed/cafe_study_v1/c_stay_s4_review_queue_786_kakao_walk.csv")
    parser.add_argument("--max-new-calls", type=int, default=900)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    api_key = os.environ.get("KAKAO_REST_API_KEY")
    if not api_key:
        raise SystemExit("KAKAO_REST_API_KEY is required; it is not stored in the repository.")
    queue = pd.read_csv(args.queue, dtype={"place_id": str, "nearest_area_code": str})
    areas = gpd.read_file(args.areas)
    output = Path(args.output)
    cache = pd.read_csv(output, dtype={"place_id": str, "nearest_area_code": str}) if output.exists() else None
    result = build_walk_access(
        queue, areas, api_key, max_new_calls=args.max_new_calls,
        sleep_seconds=args.sleep, timeout=args.timeout, existing_cache=cache,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"wrote {len(result)} rows; API routes queried at most {args.max_new_calls}")


if __name__ == "__main__":
    main()
