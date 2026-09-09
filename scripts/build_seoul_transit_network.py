#!/usr/bin/env python3
"""Convert official Seoul bus and metro source files into routing tables."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pandas as pd


def _id(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True)


def build_bus_edges(route_stops: pd.DataFrame, speeds: pd.DataFrame, hour: int = 10) -> pd.DataFrame:
    duration_column = f"운행시간_{hour:02d}시"
    required_routes = {"ROUTE_ID", "노선명", "순번", "NODE_ID", "정류소명", "X좌표", "Y좌표"}
    required_speeds = {"노선_ID", "출발_정류장_ID", "도착_정류장_ID", duration_column}
    if missing := required_routes.difference(route_stops.columns):
        raise ValueError("route-stop columns missing: " + ", ".join(sorted(missing)))
    if missing := required_speeds.difference(speeds.columns):
        raise ValueError("speed columns missing: " + ", ".join(sorted(missing)))

    routes = route_stops.copy()
    routes["route_id"] = _id(routes["ROUTE_ID"])
    routes["stop_id"] = _id(routes["NODE_ID"])
    routes["stop_sequence"] = pd.to_numeric(routes["순번"], errors="raise").astype(int)
    routes = routes.sort_values(["route_id", "stop_sequence"])
    following = routes.groupby("route_id", sort=False).shift(-1)
    adjacent = following["stop_id"].notna()
    topology = pd.DataFrame(
        {
            "route_id": routes.loc[adjacent, "route_id"],
            "route_name": routes.loc[adjacent, "노선명"].astype(str),
            "from_stop_id": routes.loc[adjacent, "stop_id"],
            "to_stop_id": following.loc[adjacent, "stop_id"],
            "from_sequence": routes.loc[adjacent, "stop_sequence"],
            "to_sequence": following.loc[adjacent, "stop_sequence"].astype(int),
        }
    )

    speed = speeds.copy()
    speed["route_id"] = _id(speed["노선_ID"])
    speed["from_stop_id"] = _id(speed["출발_정류장_ID"])
    speed["to_stop_id"] = _id(speed["도착_정류장_ID"])
    speed["duration_seconds"] = pd.to_numeric(speed[duration_column], errors="coerce").replace(0, pd.NA)
    average = (
        speed.dropna(subset=["duration_seconds"])
        .groupby(["route_id", "from_stop_id", "to_stop_id"], as_index=False)["duration_seconds"]
        .median()
    )
    result = topology.merge(average, on=["route_id", "from_stop_id", "to_stop_id"], how="left")
    fallback = speed["duration_seconds"].median()
    result["duration_source"] = result["duration_seconds"].notna().map({True: "hourly_median", False: "network_median"})
    result["duration_seconds"] = result["duration_seconds"].fillna(fallback)
    return result.sort_values(["route_id", "from_sequence"]).reset_index(drop=True)


def build_bus_stops(route_stops: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(
        {
            "stop_id": _id(route_stops["NODE_ID"]),
            "stop_name": route_stops["정류소명"].astype(str),
            "longitude": pd.to_numeric(route_stops["X좌표"], errors="coerce"),
            "latitude": pd.to_numeric(route_stops["Y좌표"], errors="coerce"),
            "mode": "bus",
        }
    )
    return result.dropna(subset=["longitude", "latitude"]).drop_duplicates("stop_id").reset_index(drop=True)


def convert_metro_timetable(raw: pd.DataFrame) -> pd.DataFrame:
    required = {
        "호선", "역사코드", "역사명", "주중주말", "방향", "급행여부", "열차코드",
        "열차도착시간", "열차출발시간", "출발역", "도착역",
    }
    if missing := required.difference(raw.columns):
        raise ValueError("metro columns missing: " + ", ".join(sorted(missing)))
    frame = raw.copy()
    identity = ["주중주말", "호선", "방향", "급행여부", "열차코드", "출발역", "도착역"]
    frame["trip_id"] = frame[identity].fillna("").astype(str).agg("_".join, axis=1)
    frame["stop_id"] = "metro_" + _id(frame["호선"]) + "_" + frame["역사코드"].astype(str).str.zfill(4)
    frame["arrival_time"] = frame["열차도착시간"].fillna(frame["열차출발시간"])
    frame["departure_time"] = frame["열차출발시간"].fillna(frame["열차도착시간"])
    frame = frame.dropna(subset=["arrival_time", "departure_time"])
    frame["_sort_time"] = frame["departure_time"].str.split(":").apply(lambda p: int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2]))
    frame = frame.sort_values(["trip_id", "_sort_time"])
    frame["stop_sequence"] = frame.groupby("trip_id").cumcount() + 1
    return frame.rename(columns={"역사명": "stop_name", "호선": "line", "주중주말": "service_type"})[
        ["trip_id", "stop_id", "stop_name", "line", "service_type", "arrival_time", "departure_time", "stop_sequence"]
    ].reset_index(drop=True)


def build_metro_stops(master: pd.DataFrame, timetable: pd.DataFrame) -> pd.DataFrame:
    frame = master.copy()
    frame["line"] = frame["호선"].astype(str).str.extract(r"(\d+)", expand=False)
    frame["station_code"] = _id(frame["역사_ID"]).str.zfill(4)
    frame["stop_id"] = "metro_" + frame["line"] + "_" + frame["station_code"]
    wanted = timetable[["stop_id", "stop_name"]].drop_duplicates().copy()
    exact = wanted.merge(
        frame[["stop_id", "역사명", "경도", "위도"]], on="stop_id", how="left"
    )
    exact["matched_by"] = exact["경도"].notna().map({True: "station_code_line", False: pd.NA})

    coordinates = frame.groupby("역사명", as_index=False).agg(
        longitude=("경도", "mean"), latitude=("위도", "mean"),
        lon_span=("경도", lambda value: value.max() - value.min()),
        lat_span=("위도", lambda value: value.max() - value.min()),
    )
    coordinates = coordinates[(coordinates["lon_span"] < 0.01) & (coordinates["lat_span"] < 0.01)]
    exact = exact.merge(coordinates, left_on="stop_name", right_on="역사명", how="left", suffixes=("", "_name"))
    exact["경도"] = exact["경도"].fillna(exact["longitude"])
    exact["위도"] = exact["위도"].fillna(exact["latitude"])
    exact["matched_by"] = exact["matched_by"].fillna("unambiguous_station_name")
    result = pd.DataFrame(
        {
            "stop_id": exact["stop_id"],
            "stop_name": exact["stop_name"].astype(str),
            "longitude": pd.to_numeric(exact["경도"], errors="coerce"),
            "latitude": pd.to_numeric(exact["위도"], errors="coerce"),
            "mode": "metro",
            "matched_by": exact["matched_by"],
        }
    )
    return result.dropna(subset=["longitude", "latitude"]).drop_duplicates("stop_id").reset_index(drop=True)


def _clock_seconds(value: str) -> int:
    hour, minute, second = (int(part) for part in str(value).split(":"))
    return hour * 3600 + minute * 60 + second


def build_metro_edges(timetable: pd.DataFrame, service_type: str = "DAY") -> pd.DataFrame:
    frame = timetable[timetable["service_type"] == service_type].copy()
    frame = frame.sort_values(["trip_id", "stop_sequence"])
    following = frame.groupby("trip_id", sort=False).shift(-1)
    valid = following["stop_id"].notna()
    edges = pd.DataFrame(
        {
            "route_id": "metro_line_" + frame.loc[valid, "line"].astype(str),
            "route_name": frame.loc[valid, "line"].astype(str) + "호선",
            "from_stop_id": frame.loc[valid, "stop_id"],
            "to_stop_id": following.loc[valid, "stop_id"],
            "duration_seconds": [
                _clock_seconds(arrival) - _clock_seconds(departure)
                for departure, arrival in zip(
                    frame.loc[valid, "departure_time"], following.loc[valid, "arrival_time"], strict=True
                )
            ],
        }
    )
    edges = edges[(edges["duration_seconds"] > 0) & (edges["duration_seconds"] < 1800)]
    return (
        edges.groupby(["route_id", "route_name", "from_stop_id", "to_stop_id"], as_index=False)["duration_seconds"]
        .median()
        .sort_values(["route_id", "from_stop_id", "to_stop_id"])
        .reset_index(drop=True)
    )


def read_speed_zip(path: Path, hour: int) -> pd.DataFrame:
    columns = ["노선_ID", "출발_정류장_ID", "도착_정류장_ID", f"운행시간_{hour:02d}시"]
    with zipfile.ZipFile(path) as archive:
        csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(csv_name) as handle:
            return pd.read_csv(handle, encoding="cp949", usecols=columns, low_memory=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus-routes", type=Path, required=True)
    parser.add_argument("--bus-speeds", type=Path, required=True)
    parser.add_argument("--metro-timetable", type=Path, required=True)
    parser.add_argument("--station-master", type=Path, required=True)
    parser.add_argument("--hour", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=Path("data/interim/local_transit"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    route_stops = pd.read_excel(args.bus_routes, sheet_name="Data")
    speeds = read_speed_zip(args.bus_speeds, args.hour)
    bus_edges = build_bus_edges(route_stops, speeds, args.hour)
    bus_stops = build_bus_stops(route_stops)
    metro_raw = pd.read_csv(args.metro_timetable, encoding="cp949", low_memory=False)
    metro_times = convert_metro_timetable(metro_raw)
    station_master = pd.read_csv(args.station_master, encoding="cp949", low_memory=False)
    metro_stops = build_metro_stops(station_master, metro_times)
    metro_edges = build_metro_edges(metro_times)

    bus_edges.to_csv(args.output_dir / f"bus_edges_{args.hour:02d}.csv", index=False, encoding="utf-8-sig")
    bus_stops.to_csv(args.output_dir / "bus_stops.csv", index=False, encoding="utf-8-sig")
    metro_times.to_csv(args.output_dir / "metro_stop_times.csv", index=False, encoding="utf-8-sig")
    metro_stops.to_csv(args.output_dir / "metro_stops.csv", index=False, encoding="utf-8-sig")
    metro_edges.to_csv(args.output_dir / "metro_edges.csv", index=False, encoding="utf-8-sig")
    summary = pd.DataFrame(
        [
            {"table": "bus_edges", "rows": len(bus_edges), "unique_nodes": pd.unique(bus_edges[["from_stop_id", "to_stop_id"]].values.ravel()).size},
            {"table": "bus_stops", "rows": len(bus_stops), "unique_nodes": bus_stops["stop_id"].nunique()},
            {"table": "metro_stop_times", "rows": len(metro_times), "unique_nodes": metro_times["stop_id"].nunique()},
            {"table": "metro_stops", "rows": len(metro_stops), "unique_nodes": metro_stops["stop_id"].nunique()},
            {"table": "metro_edges", "rows": len(metro_edges), "unique_nodes": pd.unique(metro_edges[["from_stop_id", "to_stop_id"]].values.ravel()).size},
        ]
    )
    summary.to_csv(args.output_dir / "network_build_summary.csv", index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
