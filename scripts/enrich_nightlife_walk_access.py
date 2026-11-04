#!/usr/bin/env python3
"""Validate current nightlife POIs against a 400 m Kakao walking boundary.

POIs inside a selected official area are zero-distance matches.  External POIs
whose Euclidean distance already exceeds 400 m are safely rejected without an
API call.  Only the remaining boundary cases are routed from the nearest point
on the official-area boundary.
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


def fetch_walk_route(session, api_key: str, start_x: float, start_y: float, end_x: float, end_y: float, timeout: int = 30):
    response = session.get(
        KAKAO_WALK_URL,
        headers={"Authorization": f"KakaoAK {api_key}"},
        params={"start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y, "route_mode": "SHORTEST"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    status = str(payload.get("status", "UNKNOWN_RESPONSE"))
    if status == "SAME_POINT":
        return {"route_status": status, "walk_distance_m": 0.0, "walk_time_s": 0.0}
    if status != "OK":
        return {"route_status": status, "walk_distance_m": np.nan, "walk_time_s": np.nan}
    props = payload.get("route", {}).get("properties", {})
    if "totalDistance" not in props or "totalTime" not in props:
        return {"route_status": "MALFORMED_OK_RESPONSE", "walk_distance_m": np.nan, "walk_time_s": np.nan}
    return {"route_status": "OK", "walk_distance_m": float(props["totalDistance"]), "walk_time_s": float(props["totalTime"])}


def _boundary_origins(queue: pd.DataFrame, areas: gpd.GeoDataFrame) -> pd.DataFrame:
    area_metric = areas[["area_code", "geometry"]].copy()
    area_metric["area_code"] = area_metric["area_code"].astype(str)
    area_metric = area_metric.to_crs("EPSG:5186").set_index("area_code")
    points = gpd.GeoDataFrame(
        queue.copy(), geometry=gpd.points_from_xy(queue.longitude, queue.latitude), crs="EPSG:4326"
    ).to_crs("EPSG:5186")
    origins = []
    for row in points.itertuples():
        boundary = area_metric.loc[str(row.nearest_area_code), "geometry"].boundary
        origins.append(nearest_points(row.geometry, boundary)[1])
    origin_series = gpd.GeoSeries(origins, crs="EPSG:5186").to_crs("EPSG:4326")
    result = queue.copy()
    result["boundary_origin_x"] = origin_series.x.to_numpy()
    result["boundary_origin_y"] = origin_series.y.to_numpy()
    return result


def build_walk_access(
    queue: pd.DataFrame,
    areas: gpd.GeoDataFrame,
    api_key: str,
    max_new_calls: int = 900,
    sleep_seconds: float = 0.15,
    timeout: int = 30,
    existing_cache: pd.DataFrame | None = None,
    session=None,
) -> pd.DataFrame:
    required = {"place_id", "venue_class", "longitude", "latitude", "scope_status", "nearest_area_code", "euclidean_distance_m"}
    missing = sorted(required - set(queue.columns))
    if missing:
        raise ValueError(f"queue missing columns: {', '.join(missing)}")
    out = _boundary_origins(queue, areas)
    out["place_id"] = out["place_id"].astype(str)
    out["nearest_area_code"] = out["nearest_area_code"].astype(str)
    cache = {}
    if existing_cache is not None and not existing_cache.empty:
        for row in existing_cache.itertuples():
            cache[(str(row.place_id), str(row.nearest_area_code))] = {
                "route_status": row.route_status, "walk_distance_m": row.walk_distance_m, "walk_time_s": row.walk_time_s,
            }
    requester = session or requests.Session()
    rows = []
    calls = 0
    for row in out.itertuples(index=False):
        key = (str(row.place_id), str(row.nearest_area_code))
        if row.scope_status == "INSIDE_OFFICIAL_AREA":
            route = {"route_status": "INSIDE_OFFICIAL_AREA", "walk_distance_m": 0.0, "walk_time_s": 0.0}
        elif float(row.euclidean_distance_m) > 400:
            route = {"route_status": "EUCLIDEAN_GT_400", "walk_distance_m": np.nan, "walk_time_s": np.nan}
        elif key in cache:
            route = cache[key]
        elif calls >= max_new_calls:
            route = {"route_status": "PENDING_DAILY_QUOTA", "walk_distance_m": np.nan, "walk_time_s": np.nan}
        else:
            try:
                route = fetch_walk_route(
                    requester, api_key, float(row.boundary_origin_x), float(row.boundary_origin_y),
                    float(row.longitude), float(row.latitude), timeout,
                )
            except requests.RequestException as error:
                route = {"route_status": f"REQUEST_ERROR:{type(error).__name__}", "walk_distance_m": np.nan, "walk_time_s": np.nan}
            calls += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
        rows.append({**row._asdict(), **route})
    result = pd.DataFrame(rows)
    result["walk_access_400"] = result["walk_distance_m"].le(400)
    result["target_area_code"] = np.where(
        result["scope_status"].eq("INSIDE_OFFICIAL_AREA"), result.get("area_code"), result["nearest_area_code"]
    )
    result["route_origin_definition"] = "nearest_selected_area_boundary_proxy"
    result["route_provider"] = "Kakao Map Walking Routes REST API"
    return result


def aggregate_walk_features(detail: pd.DataFrame, areas: gpd.GeoDataFrame) -> pd.DataFrame:
    accepted = detail[detail["walk_access_400"].fillna(False)].copy()
    counts = accepted.pivot_table(
        index="target_area_code", columns="venue_class", values="place_id", aggfunc="nunique", fill_value=0
    ).rename(columns={"night_food": "night_food_walk400_count", "adult_nightlife": "adult_nightlife_walk400_count"})
    base = areas[["area_code", "area_name"]].copy()
    base["area_code"] = base["area_code"].astype(str)
    result = base.drop_duplicates("area_code").merge(counts, left_on="area_code", right_index=True, how="left")
    for column in ["night_food_walk400_count", "adult_nightlife_walk400_count"]:
        if column not in result:
            result[column] = 0
        result[column] = result[column].fillna(0).astype(int)
    return result


def _load_key(env_path: Path) -> str:
    key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    if key:
        return key
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("KAKAO_REST_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("KAKAO_REST_API_KEY is required")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope-detail", default="data/processed/nightlife_poi_v1/nightlife_poi_scope_detail.csv")
    parser.add_argument("--areas", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    parser.add_argument("--env", default="services/recommendation-api/.env")
    parser.add_argument("--output-detail", default="data/processed/nightlife_poi_v1/nightlife_poi_walk400_detail.csv")
    parser.add_argument("--output-features", default="data/processed/nightlife_poi_v1/official_area_nightlife_poi_features_786.csv")
    parser.add_argument("--max-new-calls", type=int, default=900)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()
    queue = pd.read_csv(args.scope_detail, dtype={"place_id": str, "area_code": str, "nearest_area_code": str})
    areas = gpd.read_file(args.areas)
    output_detail = Path(args.output_detail)
    cache = pd.read_csv(output_detail, dtype={"place_id": str, "nearest_area_code": str}) if output_detail.exists() else None
    detail = build_walk_access(queue, areas, _load_key(Path(args.env)), args.max_new_calls, args.sleep, existing_cache=cache)
    features = aggregate_walk_features(detail, areas)
    output_detail.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output_detail, index=False, encoding="utf-8-sig")
    features.to_csv(args.output_features, index=False, encoding="utf-8-sig")
    print(f"wrote {len(detail):,} POIs and {len(features):,} area features")


if __name__ == "__main__":
    main()
