#!/usr/bin/env python3
"""Calibrate boarding waits and transfer time from official observations."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pandas as pd


def _clock_seconds(value: str) -> int:
    hour, minute, second = (int(part) for part in str(value).split(":"))
    return hour * 3600 + minute * 60 + second


def bus_route_waits(frame: pd.DataFrame, hour: int) -> pd.DataFrame:
    column = f"버스운행횟수_{hour:02d}시"
    data = frame[["노선_ID", column]].copy()
    data["route_id"] = data["노선_ID"].astype(str).str.replace(r"\.0$", "", regex=True)
    data["runs_per_hour"] = pd.to_numeric(data[column], errors="coerce")
    route = data[data["runs_per_hour"] > 0].groupby("route_id", as_index=False)["runs_per_hour"].median()
    route["wait_seconds"] = (1800 / route["runs_per_hour"]).clip(lower=60, upper=900).round().astype(int)
    route["mode"] = "bus"
    route["method"] = "half_headway_from_hourly_operations"
    return route[["route_id", "mode", "runs_per_hour", "wait_seconds", "method"]]


def metro_line_waits(frame: pd.DataFrame, hour: int) -> pd.DataFrame:
    data = frame[frame["service_type"].astype(str) == "DAY"].copy()
    data["seconds"] = data["departure_time"].map(_clock_seconds)
    data = data[(data["seconds"] >= hour * 3600) & (data["seconds"] < (hour + 1) * 3600)]
    data = data.sort_values(["line", "stop_id", "seconds"])
    data["gap"] = data.groupby(["line", "stop_id"])["seconds"].diff()
    gaps = data[(data["gap"] > 0) & (data["gap"] <= 1800)]
    route = gaps.groupby("line", as_index=False)["gap"].median().rename(columns={"gap": "headway_seconds"})
    route["route_id"] = "metro_line_" + route["line"].astype(str)
    route["runs_per_hour"] = 3600 / route["headway_seconds"]
    route["wait_seconds"] = (route["headway_seconds"] / 2).clip(lower=60, upper=900).round().astype(int)
    route["mode"] = "metro"
    route["method"] = "half_median_weekday_timetable_headway"
    return route[["route_id", "mode", "runs_per_hour", "wait_seconds", "method"]]


def weighted_transfer_median(frame: pd.DataFrame, hour: int) -> int:
    data = frame[pd.to_numeric(frame["시간대"], errors="coerce") == hour].copy()
    data["weight"] = pd.to_numeric(data["환승_수_합"], errors="coerce")
    data["seconds"] = pd.to_numeric(data["환승_시간_평균"], errors="coerce")
    data = data[(data["weight"] > 0) & (data["seconds"] > 0) & (data["seconds"] <= 3600)].sort_values("seconds")
    if data.empty:
        raise ValueError(f"no valid transfer observations for hour {hour}")
    threshold = data["weight"].sum() / 2
    return int(data.loc[data["weight"].cumsum() >= threshold, "seconds"].iloc[0])


def _read_zip(path: Path, columns: list[str]) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        name = next(item for item in archive.namelist() if item.lower().endswith(".csv"))
        with archive.open(name) as handle:
            return pd.read_csv(handle, encoding="cp949", usecols=columns, low_memory=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus-operations", type=Path, required=True)
    parser.add_argument("--metro-stop-times", type=Path, required=True)
    parser.add_argument("--transfers", type=Path, required=True)
    parser.add_argument("--hours", type=int, nargs="+", default=[8, 14, 19])
    parser.add_argument("--output-dir", type=Path, default=Path("data/interim/local_transit/calibration"))
    args = parser.parse_args()
    bus_columns = ["노선_ID"] + [f"버스운행횟수_{hour:02d}시" for hour in args.hours]
    bus = _read_zip(args.bus_operations, bus_columns)
    metro = pd.read_csv(args.metro_stop_times, dtype={"line": str, "stop_id": str})
    transfer = _read_zip(args.transfers, ["시간대", "환승_수_합", "환승_시간_평균"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for hour in args.hours:
        waits = pd.concat([bus_route_waits(bus, hour), metro_line_waits(metro, hour)], ignore_index=True)
        waits.to_csv(args.output_dir / f"route_waits_{hour:02d}.csv", index=False, encoding="utf-8-sig")
        transfer_seconds = weighted_transfer_median(transfer, hour)
        summaries.append(
            {
                "hour": hour, "route_count": len(waits), "bus_route_count": (waits["mode"] == "bus").sum(),
                "metro_route_count": (waits["mode"] == "metro").sum(),
                "median_route_wait_seconds": waits["wait_seconds"].median(),
                "observed_transfer_seconds": transfer_seconds,
            }
        )
    summary = pd.DataFrame(summaries)
    summary.to_csv(args.output_dir / "calibration_summary.csv", index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
