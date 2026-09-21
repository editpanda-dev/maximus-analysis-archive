"""Create commercial-area destination movement features from public Seoul data.

Input rows are destination administrative-dong, time, purpose and aggregated
population counts. They are not individual trajectories and do not directly
observe restaurant, cafe or study visits.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pandas as pd


PURPOSE_MAP = {
    "1": "commute",
    "2": "school",
    "3": "return_home",
    "4": "shopping",
    "5": "tourism",
    "6": "hospital",
    "7": "other",
}


def time_slot(time_code: str) -> str:
    code = str(time_code)
    hour = int(code) if len(code) <= 2 else int(code[:2])
    if 6 <= hour < 10:
        return "morning"
    if 10 <= hour < 17:
        return "daytime"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def load_movement(input_glob: str, chunksize: int = 200_000) -> pd.DataFrame:
    paths = sorted(glob.glob(input_glob))
    if not paths:
        raise FileNotFoundError(f"No files match: {input_glob}")
    collected = []
    usecols = ["d_admdong_cd", "time_cd", "move_purpose", "total_cnt", "etl_ymd"]
    for path in paths:
        for chunk in pd.read_csv(path, usecols=usecols, dtype={"d_admdong_cd": "string", "time_cd": "string", "move_purpose": "string", "etl_ymd": "string"}, chunksize=chunksize):
            chunk["move_purpose"] = chunk["move_purpose"].astype("string")
            chunk = chunk.loc[chunk["move_purpose"].isin(PURPOSE_MAP)].copy()
            chunk["admin_code"] = chunk["d_admdong_cd"].str.zfill(8)
            chunk["time_slot"] = chunk["time_cd"].map(time_slot)
            chunk["purpose"] = chunk["move_purpose"].map(PURPOSE_MAP)
            collected.append(
                chunk.groupby(["admin_code", "time_slot", "purpose", "etl_ymd"], as_index=False)["total_cnt"].sum()
            )
    return pd.concat(collected, ignore_index=True).groupby(
        ["admin_code", "time_slot", "purpose", "etl_ymd"], as_index=False
    )["total_cnt"].sum()


def build_features(movement: pd.DataFrame, overlap: pd.DataFrame, candidate_area_codes: set[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    overlap = overlap[["area_code", "admin_code", "overlap_share"]].copy()
    overlap["area_code"] = overlap["area_code"].astype("string")
    if candidate_area_codes is not None:
        overlap = overlap.loc[overlap["area_code"].isin(candidate_area_codes)].copy()
    overlap["admin_code"] = overlap["admin_code"].astype("string").str.zfill(8)
    overlap["allocation_weight"] = overlap["overlap_share"] / overlap.groupby("admin_code")["overlap_share"].transform("sum")
    joined = movement.merge(overlap, on="admin_code", how="inner")
    joined["allocated_inflow_count"] = joined["total_cnt"] * joined["allocation_weight"]
    area = joined.groupby(["area_code", "time_slot", "purpose"], as_index=False).agg(
        inflow_count=("allocated_inflow_count", "sum"),
        source_row_count=("total_cnt", "size"),
        source_date_min=("etl_ymd", "min"),
        source_date_max=("etl_ymd", "max"),
    )
    totals = area.groupby(["area_code", "time_slot"], as_index=False)["inflow_count"].sum().rename(
        columns={"inflow_count": "time_slot_inflow_total"}
    )
    area = area.merge(totals, on=["area_code", "time_slot"], how="left")
    area["purpose_share"] = area["inflow_count"] / area["time_slot_inflow_total"]
    area["source_period"] = area["source_date_min"] + "-" + area["source_date_max"]
    area = area.drop(columns=["source_date_min", "source_date_max"])
    audit = pd.DataFrame(
        [{
            "input_total_count": movement["total_cnt"].sum(),
            "matched_total_count": movement.merge(overlap[["admin_code"]].drop_duplicates(), on="admin_code", how="inner")["total_cnt"].sum(),
            "allocated_total_count": area["inflow_count"].sum(),
            "input_admin_dong_count": movement["admin_code"].nunique(),
            "matched_admin_dong_count": joined["admin_code"].nunique(),
            "area_count": area["area_code"].nunique(),
            "source_date_min": movement["etl_ymd"].min(),
            "source_date_max": movement["etl_ymd"].max(),
        }]
    )
    return area.sort_values(["area_code", "time_slot", "purpose"]), audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-glob", required=True, help="Public monthly CSV glob, not committed to Git")
    parser.add_argument("--overlap", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_dong_overlap.csv"))
    parser.add_argument("--candidates", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/living_movement"))
    args = parser.parse_args()
    movement = load_movement(args.input_glob)
    overlap = pd.read_csv(args.overlap, dtype={"admin_code": "string", "area_code": "string"})
    with args.candidates.open() as file:
        candidate_codes = {
            str(feature["properties"]["area_code"])
            for feature in json.load(file)["features"]
        }
    features, audit = build_features(movement, overlap, candidate_codes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output_dir / "official_area_living_movement_features.csv", index=False)
    audit.to_csv(args.output_dir / "living_movement_join_audit.csv", index=False)
    print(f"Wrote {len(features):,} feature rows for {audit.loc[0, 'area_count']:,} areas")


if __name__ == "__main__":
    main()
