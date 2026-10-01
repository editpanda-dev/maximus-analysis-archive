#!/usr/bin/env python3
"""Compute a 30-minute bus/metro accessibility pilot without a routing API.

This is a frequency/average-time model: bus edge times are hourly medians and
metro edge times are weekday timetable medians. Boarding waits and transfer
penalties are explicit assumptions in the output.
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

from local_transit_accessibility import haversine_m


def build_ride_adjacency(edges: pd.DataFrame) -> dict[str, list[tuple[str, str, int, str]]]:
    adjacency: dict[str, list[tuple[str, str, int, str]]] = defaultdict(list)
    for row in edges.itertuples(index=False):
        adjacency[str(row.from_stop_id)].append(
            (str(row.to_stop_id), str(row.route_id), max(1, round(float(row.duration_seconds))), str(row.mode))
        )
    return dict(adjacency)


def filter_active_routes(edges: pd.DataFrame, route_wait_seconds: dict[str, int]) -> pd.DataFrame:
    if not route_wait_seconds:
        return edges
    return edges[edges["route_id"].astype(str).isin(route_wait_seconds)].copy()


def route_from_access(
    ride_adjacency: dict[str, list[tuple[str, str, int, str]]],
    walking_adjacency: dict[str, list[tuple[str, int]]],
    access_times: dict[str, int],
    cutoff_seconds: int,
    wait_seconds: dict[str, int],
    transfer_penalty_seconds: int,
    route_wait_seconds: dict[str, int] | None = None,
) -> dict[str, int]:
    best_state: dict[tuple[str, str | None], int] = {}
    best_stop: dict[str, int] = {}
    queue: list[tuple[int, int, str, str | None]] = []
    sequence = itertools.count()
    for stop_id, duration in access_times.items():
        if duration <= cutoff_seconds:
            state = (str(stop_id), None)
            best_state[state] = int(duration)
            heapq.heappush(queue, (int(duration), next(sequence), str(stop_id), None))
    while queue:
        elapsed, _, stop_id, current_route = heapq.heappop(queue)
        if elapsed != best_state.get((stop_id, current_route)):
            continue
        best_stop[stop_id] = min(best_stop.get(stop_id, math.inf), elapsed)
        for target, duration in walking_adjacency.get(stop_id, []):
            candidate = elapsed + duration
            state = (target, None)
            if candidate <= cutoff_seconds and candidate < best_state.get(state, math.inf):
                best_state[state] = candidate
                heapq.heappush(queue, (candidate, next(sequence), target, None))
        for target, route_id, ride_seconds, mode in ride_adjacency.get(stop_id, []):
            if current_route == route_id:
                boarding = 0
            else:
                boarding = (route_wait_seconds or {}).get(route_id, wait_seconds.get(mode, 300))
                if current_route is not None:
                    boarding += transfer_penalty_seconds
            candidate = elapsed + boarding + ride_seconds
            state = (target, route_id)
            if candidate <= cutoff_seconds and candidate < best_state.get(state, math.inf):
                best_state[state] = candidate
                heapq.heappush(queue, (candidate, next(sequence), target, route_id))
    return {stop: int(duration) for stop, duration in best_stop.items()}


def _grid_key(longitude: float, latitude: float, cell_degrees: float) -> tuple[int, int]:
    return int(longitude // cell_degrees), int(latitude // cell_degrees)


def build_spatial_grid(stops: pd.DataFrame, cell_degrees: float = 0.005) -> dict[tuple[int, int], list[int]]:
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, row in stops.iterrows():
        grid[_grid_key(float(row.longitude), float(row.latitude), cell_degrees)].append(index)
    return dict(grid)


def nearby_stops(
    longitude: float,
    latitude: float,
    stops: pd.DataFrame,
    grid: dict[tuple[int, int], list[int]],
    radius_m: float,
    walk_speed_mps: float,
    cell_degrees: float = 0.005,
) -> dict[str, int]:
    x, y = _grid_key(longitude, latitude, cell_degrees)
    cells = math.ceil(radius_m / 450.0)
    result: dict[str, int] = {}
    for dx in range(-cells, cells + 1):
        for dy in range(-cells, cells + 1):
            for index in grid.get((x + dx, y + dy), []):
                stop = stops.loc[index]
                distance = haversine_m(longitude, latitude, float(stop.longitude), float(stop.latitude))
                if distance <= radius_m:
                    result[str(stop.stop_id)] = math.ceil(distance / walk_speed_mps)
    return result


def build_walking_adjacency(
    stops: pd.DataFrame, radius_m: float, walk_speed_mps: float
) -> dict[str, list[tuple[str, int]]]:
    grid = build_spatial_grid(stops)
    adjacency: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in stops.itertuples(index=False):
        nearby = nearby_stops(float(row.longitude), float(row.latitude), stops, grid, radius_m, walk_speed_mps)
        for target, duration in nearby.items():
            if target != str(row.stop_id):
                adjacency[str(row.stop_id)].append((target, duration))
    return dict(adjacency)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-dir", type=Path, default=Path("data/interim/local_transit"))
    parser.add_argument("--origins", type=Path, default=Path("data/external/odsay_origins.csv"))
    parser.add_argument("--districts", type=Path, default=Path("data/external/seoul_administrative_dongs_20260701.geojson"))
    parser.add_argument("--hour", type=int, default=10)
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--origin-walk-m", type=float, default=600)
    parser.add_argument("--transfer-walk-m", type=float, default=250)
    parser.add_argument("--walk-speed-mps", type=float, default=1.2)
    parser.add_argument("--bus-wait-seconds", type=int, default=300)
    parser.add_argument("--metro-wait-seconds", type=int, default=180)
    parser.add_argument("--transfer-penalty-seconds", type=int, default=120)
    parser.add_argument("--route-waits", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/local_transit_30min"))
    args = parser.parse_args()

    bus_edges = pd.read_csv(args.network_dir / f"bus_edges_{args.hour:02d}.csv", dtype={"route_id": str, "from_stop_id": str, "to_stop_id": str})
    metro_edges = pd.read_csv(args.network_dir / "metro_edges.csv", dtype={"route_id": str, "from_stop_id": str, "to_stop_id": str})
    bus_edges["mode"] = "bus"
    metro_edges["mode"] = "metro"
    edges = pd.concat([bus_edges, metro_edges], ignore_index=True)
    route_wait_seconds: dict[str, int] = {}
    if args.route_waits:
        wait_table = pd.read_csv(args.route_waits, dtype={"route_id": str})
        route_wait_seconds = dict(zip(wait_table["route_id"], wait_table["wait_seconds"].astype(int), strict=True))
        edges = filter_active_routes(edges, route_wait_seconds)
    bus_stops = pd.read_csv(args.network_dir / "bus_stops.csv", dtype={"stop_id": str})
    metro_stops = pd.read_csv(args.network_dir / "metro_stops.csv", dtype={"stop_id": str})
    stops = pd.concat([bus_stops, metro_stops], ignore_index=True).drop_duplicates("stop_id").reset_index(drop=True)
    valid = set(stops["stop_id"])
    edges = edges[edges["from_stop_id"].isin(valid) & edges["to_stop_id"].isin(valid)]

    ride_adjacency = build_ride_adjacency(edges)
    walking_adjacency = build_walking_adjacency(stops, args.transfer_walk_m, args.walk_speed_mps)
    grid = build_spatial_grid(stops)
    origins = pd.read_csv(args.origins, dtype={"origin_id": str})
    records: list[dict[str, object]] = []
    for number, origin in enumerate(origins.itertuples(index=False), start=1):
        access = nearby_stops(float(origin.longitude), float(origin.latitude), stops, grid, args.origin_walk_m, args.walk_speed_mps)
        reached = route_from_access(
            ride_adjacency, walking_adjacency, access, args.minutes * 60,
            {"bus": args.bus_wait_seconds, "metro": args.metro_wait_seconds}, args.transfer_penalty_seconds,
            route_wait_seconds,
        )
        for stop_id, elapsed in reached.items():
            records.append({"origin_id": origin.origin_id, "origin_name": origin.origin_name, "stop_id": stop_id, "travel_minutes": round(elapsed / 60, 2)})
        if number % 25 == 0 or number == len(origins):
            print(f"[{number}/{len(origins)}] origin-stop pairs: {len(records):,}")

    reachable = pd.DataFrame(records).merge(stops, on="stop_id", how="left")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reachable.to_csv(args.output_dir / "reachable_stops_by_origin.csv", index=False, encoding="utf-8-sig")

    import geopandas as gpd

    districts = gpd.read_file(args.districts).to_crs(4326)
    points = gpd.GeoDataFrame(reachable, geometry=gpd.points_from_xy(reachable.longitude, reachable.latitude), crs=4326)
    joined = gpd.sjoin(points, districts, how="inner", predicate="within").drop(columns=["geometry", "index_right"])
    joined.to_csv(args.output_dir / "reachable_dongs_by_origin.csv", index=False, encoding="utf-8-sig")
    district_columns = [column for column in districts.columns if column != "geometry"]
    group_columns = district_columns + ["mode"]
    summary = joined.groupby(group_columns, dropna=False, as_index=False).agg(
        reachable_origin_count=("origin_id", "nunique"),
        reachable_stop_count=("stop_id", "nunique"),
        median_travel_minutes=("travel_minutes", "median"),
        minimum_travel_minutes=("travel_minutes", "min"),
    )
    summary["total_origin_count"] = origins["origin_id"].nunique()
    summary["reachable_origin_ratio"] = summary["reachable_origin_count"] / summary["total_origin_count"]
    summary.to_csv(args.output_dir / "reachable_dongs_summary.csv", index=False, encoding="utf-8-sig")
    dong_keys = [column for column in district_columns if column not in {"area"}]
    candidates = summary.groupby(dong_keys, dropna=False, as_index=False).agg(
        reachable_origin_count=("reachable_origin_count", "max"),
        reachable_stop_count=("reachable_stop_count", "sum"),
        minimum_travel_minutes=("minimum_travel_minutes", "min"),
        median_travel_minutes=("median_travel_minutes", "median"),
    )
    candidates["total_origin_count"] = origins["origin_id"].nunique()
    candidates["reachable_origin_ratio"] = candidates["reachable_origin_count"] / candidates["total_origin_count"]
    candidates["candidate_tier"] = pd.cut(
        candidates["reachable_origin_ratio"],
        bins=[-0.001, 0.25, 0.50, 0.80, 1.001],
        labels=["excluded_below_25pct", "broad_25pct", "base_50pct", "stable_80pct"],
        right=False,
    )
    candidates.sort_values(["reachable_origin_ratio", "median_travel_minutes"], ascending=[False, True]).to_csv(
        args.output_dir / "candidate_dongs.csv", index=False, encoding="utf-8-sig"
    )
    assumptions = pd.DataFrame(
        [{
            "model": "hourly-average static multimodal graph", "analysis_hour": args.hour,
            "cutoff_minutes": args.minutes, "origin_walk_m": args.origin_walk_m,
            "transfer_walk_m": args.transfer_walk_m, "walk_speed_mps": args.walk_speed_mps,
            "bus_wait_seconds": args.bus_wait_seconds, "metro_wait_seconds": args.metro_wait_seconds,
            "transfer_penalty_seconds": args.transfer_penalty_seconds,
            "route_specific_wait_count": len(route_wait_seconds),
        }]
    )
    assumptions.to_csv(args.output_dir / "model_assumptions.csv", index=False, encoding="utf-8-sig")
    print(f"saved {len(reachable):,} pairs, {len(summary):,} dong-mode summaries, and {len(candidates):,} candidate dongs")


if __name__ == "__main__":
    main()
