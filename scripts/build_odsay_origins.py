#!/usr/bin/env python3
"""Build the current Dongdaemun origin universe from bus and subway sources."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bus-xlsx", type=Path, required=True)
    parser.add_argument("--subway-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/external/odsay_origins.csv"))
    parser.add_argument("--all-bus-output", type=Path, default=Path("data/interim/seoul_bus_stops_20260902.csv"))
    args = parser.parse_args()

    bus = pd.read_excel(args.bus_xlsx, sheet_name="Data")
    required = {"NODE_ID", "ARS_ID", "정류소명", "X좌표", "Y좌표"}
    if not required.issubset(bus.columns):
        raise SystemExit(f"missing bus columns: {sorted(required - set(bus.columns))}")
    bus["ARS_ID"] = pd.to_numeric(bus["ARS_ID"], errors="coerce")
    bus = bus.dropna(subset=["NODE_ID", "ARS_ID", "X좌표", "Y좌표"]).copy()
    bus["ARS_ID"] = bus["ARS_ID"].astype(int)

    all_bus = pd.DataFrame({
        "stop_id": "bus_" + bus["NODE_ID"].astype(str),
        "stop_name": bus["정류소명"].astype(str),
        "longitude": bus["X좌표"].astype(float),
        "latitude": bus["Y좌표"].astype(float),
        "stop_type": "bus",
        "ars_id": bus["ARS_ID"].astype(str).str.zfill(5),
    })
    args.all_bus_output.parent.mkdir(parents=True, exist_ok=True)
    all_bus.to_csv(args.all_bus_output, index=False, encoding="utf-8-sig")

    ddm = bus[bus["ARS_ID"].between(6000, 6999)].copy()
    bus_origins = pd.DataFrame({
        "origin_id": "bus_" + ddm["NODE_ID"].astype(str),
        "origin_name": ddm["정류소명"].astype(str),
        "longitude": ddm["X좌표"].astype(float),
        "latitude": ddm["Y좌표"].astype(float),
        "origin_type": "bus",
        "source": "Seoul OA-15067 20260902",
    })
    subway = pd.read_csv(args.subway_csv, encoding="utf-8-sig")
    subway_origins = subway[[
        "origin_id", "origin_name", "longitude", "latitude", "origin_type", "source"
    ]].copy()
    origins = pd.concat([bus_origins, subway_origins], ignore_index=True)
    if origins["origin_id"].duplicated().any():
        raise SystemExit("duplicate origin_id detected")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    origins.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"saved {len(bus_origins)} bus + {len(subway_origins)} subway = {len(origins)} origins")


if __name__ == "__main__":
    main()
