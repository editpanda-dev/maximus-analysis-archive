#!/usr/bin/env python3
"""Local, quota-free GTFS public-transit accessibility calculator.

The routing core uses a scheduled connection scan.  It is intentionally
independent of any map API: the only network input is a standard GTFS feed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import pandas as pd


REQUIRED_GTFS_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")


def parse_gtfs_time(value: str) -> int:
    """Convert a GTFS HH:MM:SS value, including hours >= 24, to seconds."""
    parts = str(value).strip().split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid GTFS time: {value!r}")
    hours, minutes, seconds = (int(part) for part in parts)
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise ValueError(f"invalid GTFS time: {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def _gtfs_names(source: Path) -> set[str]:
    if source.is_dir():
        return {path.name for path in source.iterdir() if path.is_file()}
    if source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            return {Path(name).name for name in archive.namelist() if not name.endswith("/")}
    raise ValueError(f"GTFS source must be a directory or ZIP file: {source}")


def validate_gtfs(source: Path) -> dict[str, bool]:
    names = _gtfs_names(Path(source))
    missing = [name for name in REQUIRED_GTFS_FILES if name not in names]
    if missing:
        raise ValueError("missing required GTFS file(s): " + ", ".join(missing))
    return {name: name in names for name in REQUIRED_GTFS_FILES + ("calendar.txt", "calendar_dates.txt", "transfers.txt")}


def _read_gtfs_table(source: Path, name: str, **kwargs) -> pd.DataFrame:
    source = Path(source)
    if source.is_dir():
        return pd.read_csv(source / name, dtype=str, **kwargs)
    with zipfile.ZipFile(source) as archive:
        matches = [entry for entry in archive.namelist() if Path(entry).name == name]
        if not matches:
            raise FileNotFoundError(name)
        with archive.open(matches[0]) as handle:
            return pd.read_csv(handle, dtype=str, **kwargs)


def build_connections(stop_times: pd.DataFrame) -> pd.DataFrame:
    """Build consecutive vehicle movements sorted by departure time."""
    required = {"trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"}
    missing = required.difference(stop_times.columns)
    if missing:
        raise ValueError("stop_times is missing columns: " + ", ".join(sorted(missing)))
    frame = stop_times[list(required)].copy()
    frame["stop_sequence"] = pd.to_numeric(frame["stop_sequence"], errors="raise")
    frame["arrival_seconds"] = frame["arrival_time"].map(parse_gtfs_time)
    frame["departure_seconds"] = frame["departure_time"].map(parse_gtfs_time)
    frame = frame.sort_values(["trip_id", "stop_sequence"])
    following = frame.groupby("trip_id", sort=False).shift(-1)
    valid = following["stop_id"].notna()
    result = pd.DataFrame(
        {
            "trip_id": frame.loc[valid, "trip_id"],
            "from_stop_id": frame.loc[valid, "stop_id"],
            "to_stop_id": following.loc[valid, "stop_id"],
            "departure_seconds": frame.loc[valid, "departure_seconds"],
            "arrival_seconds": following.loc[valid, "arrival_seconds"],
        }
    )
    return result.sort_values("departure_seconds").reset_index(drop=True)


def select_active_service_ids(
    calendar: pd.DataFrame | None,
    calendar_dates: pd.DataFrame | None,
    service_date: str,
) -> set[str]:
    """Resolve GTFS services active on an ISO-formatted date."""
    target = dt.date.fromisoformat(service_date)
    compact = target.strftime("%Y%m%d")
    active: set[str] = set()
    if calendar is not None and not calendar.empty:
        weekday = target.strftime("%A").lower()
        within = (calendar["start_date"] <= compact) & (calendar["end_date"] >= compact)
        running = calendar[weekday].astype(str) == "1"
        active.update(calendar.loc[within & running, "service_id"].astype(str))
    if calendar_dates is not None and not calendar_dates.empty:
        today = calendar_dates[calendar_dates["date"].astype(str) == compact]
        active.update(today.loc[today["exception_type"].astype(str) == "1", "service_id"].astype(str))
        active.difference_update(today.loc[today["exception_type"].astype(str) == "2", "service_id"].astype(str))
    return active


def earliest_arrivals(
    connections: pd.DataFrame,
    access_times: dict[str, int],
    departure_time: int,
    cutoff_seconds: int = 1800,
    transfer_edges: dict[str, list[tuple[str, int]]] | None = None,
) -> dict[str, int]:
    """Return earliest stop arrival times within a cutoff.

    Same-stop vehicle changes are naturally allowed. Explicit walking transfer
    edges are relaxed whenever a stop becomes reachable.
    """
    deadline = departure_time + cutoff_seconds
    arrivals = {
        str(stop_id): departure_time + int(seconds)
        for stop_id, seconds in access_times.items()
        if departure_time + int(seconds) <= deadline
    }
    transfer_edges = transfer_edges or {}

    def relax_walks(seed: str) -> None:
        queue = [seed]
        while queue:
            current = queue.pop()
            current_time = arrivals[current]
            for target, duration in transfer_edges.get(current, []):
                candidate = current_time + int(duration)
                if candidate <= deadline and candidate < arrivals.get(str(target), math.inf):
                    arrivals[str(target)] = candidate
                    queue.append(str(target))

    for stop_id in list(arrivals):
        relax_walks(stop_id)
    for row in connections.itertuples(index=False):
        if row.departure_seconds > deadline:
            break
        if arrivals.get(str(row.from_stop_id), math.inf) <= row.departure_seconds:
            target = str(row.to_stop_id)
            if row.arrival_seconds <= deadline and row.arrival_seconds < arrivals.get(target, math.inf):
                arrivals[target] = int(row.arrival_seconds)
                relax_walks(target)
    return arrivals


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def origin_access_times(origin: pd.Series, stops: pd.DataFrame, radius_m: float, walk_speed_mps: float) -> dict[str, int]:
    result: dict[str, int] = {}
    for stop in stops.itertuples(index=False):
        distance = haversine_m(float(origin.longitude), float(origin.latitude), float(stop.stop_lon), float(stop.stop_lat))
        if distance <= radius_m:
            result[str(stop.stop_id)] = math.ceil(distance / walk_speed_mps)
    return result


def load_transfer_edges(source: Path) -> dict[str, list[tuple[str, int]]]:
    if "transfers.txt" not in _gtfs_names(source):
        return {}
    transfers = _read_gtfs_table(source, "transfers.txt")
    edges: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in transfers.itertuples(index=False):
        duration = int(getattr(row, "min_transfer_time", 0) or 0)
        edges[str(row.from_stop_id)].append((str(row.to_stop_id), duration))
    return dict(edges)


def run_pipeline(args: argparse.Namespace) -> None:
    validate_gtfs(args.gtfs)
    stops = _read_gtfs_table(args.gtfs, "stops.txt")
    stop_times = _read_gtfs_table(args.gtfs, "stop_times.txt")
    trips = _read_gtfs_table(args.gtfs, "trips.txt")
    names = _gtfs_names(args.gtfs)
    calendar = _read_gtfs_table(args.gtfs, "calendar.txt") if "calendar.txt" in names else None
    calendar_dates = _read_gtfs_table(args.gtfs, "calendar_dates.txt") if "calendar_dates.txt" in names else None
    active_services = select_active_service_ids(calendar, calendar_dates, args.service_date)
    if active_services:
        active_trips = set(trips.loc[trips["service_id"].isin(active_services), "trip_id"].astype(str))
        stop_times = stop_times[stop_times["trip_id"].isin(active_trips)]
    elif calendar is not None or calendar_dates is not None:
        raise ValueError(f"no active GTFS service found for {args.service_date}")
    connections = build_connections(stop_times)
    transfers = load_transfer_edges(args.gtfs)
    origins = pd.read_csv(args.origins, dtype={"origin_id": str})
    departure = parse_gtfs_time(args.departure_time)
    records: list[dict[str, object]] = []
    for origin in origins.itertuples(index=False):
        origin_series = pd.Series(origin._asdict())
        access = origin_access_times(origin_series, stops, args.access_radius_m, args.walk_speed_mps)
        arrivals = earliest_arrivals(connections, access, departure, args.minutes * 60, transfers)
        for stop_id, arrival in arrivals.items():
            records.append(
                {
                    "origin_id": str(origin.origin_id),
                    "origin_name": origin.origin_name,
                    "stop_id": stop_id,
                    "arrival_seconds": arrival,
                    "travel_minutes": round((arrival - departure) / 60, 2),
                }
            )
    reachable = pd.DataFrame(records).merge(stops[["stop_id", "stop_name", "stop_lon", "stop_lat"]], on="stop_id", how="left")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reachable.to_csv(args.output_dir / "reachable_stops_by_origin.csv", index=False, encoding="utf-8-sig")

    if args.districts:
        import geopandas as gpd

        districts = gpd.read_file(args.districts).to_crs(4326)
        points = gpd.GeoDataFrame(
            reachable,
            geometry=gpd.points_from_xy(reachable["stop_lon"], reachable["stop_lat"]),
            crs=4326,
        )
        joined = gpd.sjoin(points, districts, how="inner", predicate="within").drop(columns=["geometry", "index_right"])
        joined.to_csv(args.output_dir / "reachable_dongs_by_origin.csv", index=False, encoding="utf-8-sig")
    print(f"saved {len(reachable):,} origin-stop pairs to {args.output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gtfs", type=Path, required=True)
    parser.add_argument("--check-feed", action="store_true")
    parser.add_argument("--origins", type=Path)
    parser.add_argument("--districts", type=Path)
    parser.add_argument("--departure-time", default="10:00:00")
    parser.add_argument("--service-date", default=dt.date.today().isoformat())
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--access-radius-m", type=float, default=600)
    parser.add_argument("--walk-speed-mps", type=float, default=1.2)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/local_transit_30min"))
    args = parser.parse_args()
    if args.check_feed:
        print(validate_gtfs(args.gtfs))
        return
    if args.origins is None:
        parser.error("--origins is required unless --check-feed is used")
    run_pipeline(args)


if __name__ == "__main__":
    main()
