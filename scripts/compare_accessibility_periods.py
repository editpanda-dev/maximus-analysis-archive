#!/usr/bin/env python3
"""Compare calibrated accessibility candidates across analysis hours."""

from __future__ import annotations

import argparse
from functools import reduce
from pathlib import Path

import pandas as pd


def combine_periods(frames: dict[int, pd.DataFrame], threshold: float = 0.5) -> pd.DataFrame:
    keys = ["emdcd", "emdnm", "sggnm"]
    tables = []
    for hour, frame in sorted(frames.items()):
        table = frame[keys + ["reachable_origin_ratio"]].copy()
        table = table.rename(columns={"reachable_origin_ratio": f"ratio_{hour:02d}"})
        tables.append(table)
    result = reduce(lambda left, right: left.merge(right, on=keys, how="outer"), tables).fillna(0)
    ratio_columns = [column for column in result.columns if column.startswith("ratio_")]
    result["periods_above_threshold"] = (result[ratio_columns] >= threshold).sum(axis=1)
    result["minimum_period_ratio"] = result[ratio_columns].min(axis=1)
    result["mean_period_ratio"] = result[ratio_columns].mean(axis=1)
    result["time_stability"] = result["periods_above_threshold"].map(
        {0: "below_threshold", 1: "one_period", 2: "two_periods", 3: "all_three_periods"}
    )
    return result.sort_values(["periods_above_threshold", "minimum_period_ratio", "mean_period_ratio"], ascending=False).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/processed/local_transit_30min"))
    parser.add_argument("--hours", type=int, nargs="+", default=[8, 14, 19])
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--output", type=Path, default=Path("data/processed/local_transit_30min/time_period_candidates.csv"))
    args = parser.parse_args()
    frames = {hour: pd.read_csv(args.root / f"h{hour:02d}" / "candidate_dongs.csv") for hour in args.hours}
    result = combine_periods(frames, args.threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(result["time_stability"].value_counts().to_string())


if __name__ == "__main__":
    main()
