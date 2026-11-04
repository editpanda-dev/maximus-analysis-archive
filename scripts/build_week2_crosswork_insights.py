"""Build a cautious Week 2 integration table from the three team deliverables.

The movement file is a destination-area aggregate with mixed source periods.
It is retained as a context proxy only, not as a Dongdaemun-origin choice label.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{label} is missing columns: {sorted(missing)}")


def build_integrated_features(
    accessibility_path: Path,
    study_features_path: Path,
    movement_path: Path,
) -> tuple[pd.DataFrame, dict[str, float | int]]:
    """Join 786-area access, study-stay feature, and movement-context outputs."""
    access = pd.read_csv(accessibility_path, dtype={"area_code": "string"})
    study = pd.read_csv(study_features_path, dtype={"area_code": "string"})
    movement = pd.read_csv(movement_path, dtype={"area_code": "string"})
    _require_columns(
        access,
        {"area_code", "area_name", "primary_district_name", "minimum_period_ratio", "access_tier"},
        "accessibility input",
    )
    _require_columns(
        study,
        {
            "area_code",
            "study_stay_current_score",
            "study_stay_current_rank",
            "study_public_inside_count",
            "study_public_nearby_only_count",
            "study_cafe_inside_count",
        },
        "study feature input",
    )
    _require_columns(movement, {"area_code", "purpose", "inflow_count", "source_period"}, "movement input")

    movement_wide = movement.pivot_table(
        index="area_code", columns="purpose", values="inflow_count", aggfunc="sum", fill_value=0
    )
    movement_wide.columns = [f"movement_inflow_{name}" for name in movement_wide.columns]
    movement_wide = movement_wide.reset_index()
    inflow_columns = [column for column in movement_wide.columns if column.startswith("movement_inflow_")]
    movement_wide["movement_inflow_total"] = movement_wide[inflow_columns].sum(axis=1)

    def share(name: str) -> pd.Series:
        column = f"movement_inflow_{name}"
        values = movement_wide[column] if column in movement_wide else 0
        return values / movement_wide["movement_inflow_total"].where(movement_wide["movement_inflow_total"].gt(0))

    movement_wide["movement_school_share"] = share("school").fillna(0)
    movement_wide["movement_nonroutine_share"] = (share("school") + share("tourism") + share("other")).fillna(0)
    movement_wide["movement_commute_return_share"] = (share("commute") + share("return_home")).fillna(0)

    feature_columns = [
        "area_code",
        "study_stay_current_score",
        "study_stay_current_rank",
        "study_public_inside_count",
        "study_public_nearby_only_count",
        "study_cafe_inside_count",
    ]
    output = access[
        ["area_code", "area_name", "primary_district_name", "minimum_period_ratio", "access_tier"]
    ].merge(study[feature_columns], on="area_code", how="left", validate="one_to_one")
    output = output.merge(movement_wide, on="area_code", how="left", validate="one_to_one")

    score_q75 = output["study_stay_current_score"].quantile(0.75)
    school_q75 = output["movement_school_share"].quantile(0.75)
    stable_access = output["access_tier"].eq("core_80pct_all_periods")
    high_supply = output["study_stay_current_score"].ge(score_q75)
    high_school_signal = output["movement_school_share"].ge(school_q75)
    output["integration_segment"] = "monitor"
    output.loc[high_supply & ~high_school_signal, "integration_segment"] = "feature_rich_validation_needed"
    output.loc[stable_access & ~high_supply & high_school_signal, "integration_segment"] = "demand_signal_feature_gap"
    output.loc[stable_access & high_supply & high_school_signal, "integration_segment"] = "study_ready_signal"
    output["study_score_q75"] = score_q75
    output["movement_school_share_q75"] = school_q75
    output["movement_context_usage"] = "destination-context-proxy-only"

    summary: dict[str, float | int] = {
        "area_count": int(len(output)),
        "living_movement_period_count": int(movement["source_period"].nunique()),
        "study_score_q75": float(score_q75),
        "movement_school_share_q75": float(school_q75),
        "study_ready_signal_count": int(output["integration_segment"].eq("study_ready_signal").sum()),
        "demand_signal_feature_gap_count": int(output["integration_segment"].eq("demand_signal_feature_gap").sum()),
        "feature_rich_validation_needed_count": int(
            output["integration_segment"].eq("feature_rich_validation_needed").sum()
        ),
        "study_score_school_share_spearman": float(
            output[["study_stay_current_score", "movement_school_share"]].corr(method="spearman").iloc[0, 1]
        ),
        "study_score_access_spearman": float(
            output[["study_stay_current_score", "minimum_period_ratio"]].corr(method="spearman").iloc[0, 1]
        ),
    }
    return output.sort_values(["study_stay_current_rank", "area_code"]), summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--accessibility",
        type=Path,
        default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv"),
    )
    parser.add_argument(
        "--study-features",
        type=Path,
        default=Path("data/processed/study_stay_poi_enrichment/official_area_study_stay_enriched_current.csv"),
    )
    parser.add_argument(
        "--movement",
        type=Path,
        default=Path("data/processed/living_movement/official_area_living_movement_features.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/week2_integration/official_area_week2_integration.csv"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("data/processed/week2_integration/week2_integration_summary.json"),
    )
    args = parser.parse_args()
    output, summary = build_integrated_features(args.accessibility, args.study_features, args.movement)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(output):,} area rows to {args.output}")


if __name__ == "__main__":
    main()
