#!/usr/bin/env python3
"""Build auditable cafe/study follow-up outputs without claiming final v1 ranking.

The script does two independent jobs:
1. maps the C_stay/S4 review queue to the current 786 official-area scope;
2. applies an area-and-total-store residual correction to the cafe draft.

Euclidean distance is retained only as a *pre-network legacy filter*.  It is
explicitly not a replacement for the pending pedestrian-network calculation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


def _percentile(values: pd.Series) -> pd.Series:
    """Return deterministic 0--100 percentiles for a numeric signal."""
    values = values.astype(float)
    if values.nunique(dropna=True) <= 1:
        return pd.Series(50.0, index=values.index)
    return values.rank(method="average", pct=True) * 100.0


def _rank_eligible(frame: pd.DataFrame, score_column: str, status: str) -> pd.Series:
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    mask = frame["recommendation_eligible"].fillna(False) & frame["score_status"].eq(status)
    mask &= frame[score_column].notna()
    ordered = frame.loc[mask, ["area_code", score_column]].sort_values(
        [score_column, "area_code"], ascending=[False, True]
    )
    result.loc[ordered.index] = np.arange(1, len(ordered) + 1, dtype=float)
    return result


def _residual_percentile(frame: pd.DataFrame, count_column: str) -> pd.Series:
    """Residualize log store count against polygon area and all-store scale."""
    area = frame["area_km2"].clip(lower=0.02).astype(float)
    total = frame["total_stores_2025q4"].clip(lower=0).astype(float)
    target = np.log1p(frame[count_column].clip(lower=0).astype(float))
    design = np.column_stack([np.ones(len(frame)), np.log(area), np.log1p(total)])
    coefficients, *_ = np.linalg.lstsq(design, target.to_numpy(), rcond=None)
    residual = target.to_numpy() - design @ coefficients
    return _percentile(pd.Series(residual, index=frame.index))


def add_size_adjusted_scores(draft: pd.DataFrame) -> pd.DataFrame:
    """Add size-corrected cafe scores while preserving cohort separation."""
    required = {
        "area_code", "area_km2", "total_stores_2025q4", "coffee_stores", "bakery_stores",
        "coffee_supply_score", "bakery_supply_score", "coffee_full_score", "bakery_full_score",
        "score_status", "recommendation_eligible",
    }
    missing = sorted(required - set(draft.columns))
    if missing:
        raise ValueError(f"missing draft columns: {', '.join(missing)}")

    out = draft.copy()
    out["area_code"] = out["area_code"].astype(str)
    if out["area_code"].duplicated().any():
        raise ValueError("duplicate area_code in cafe study draft")
    out["coffee_size_adjusted_supply_score"] = _residual_percentile(out, "coffee_stores")
    out["bakery_size_adjusted_supply_score"] = _residual_percentile(out, "bakery_stores")
    out["cafe_size_adjusted_supply_only_score"] = (
        0.70 * out["coffee_size_adjusted_supply_score"]
        + 0.30 * out["bakery_size_adjusted_supply_score"]
    )

    # The existing full score consists of 70% supply + 30% observed sales.
    # Recover that sales component and replace only the supply component.
    coffee_sales_component = (out["coffee_full_score"] - 0.70 * out["coffee_supply_score"]) / 0.30
    bakery_sales_component = (out["bakery_full_score"] - 0.70 * out["bakery_supply_score"]) / 0.30
    out["coffee_size_adjusted_full_score"] = (
        0.70 * out["coffee_size_adjusted_supply_score"] + 0.30 * coffee_sales_component
    )
    out["bakery_size_adjusted_full_score"] = (
        0.70 * out["bakery_size_adjusted_supply_score"] + 0.30 * bakery_sales_component
    )
    out["cafe_size_adjusted_full_score"] = (
        0.70 * out["coffee_size_adjusted_full_score"]
        + 0.30 * out["bakery_size_adjusted_full_score"]
    )
    out.loc[~out["score_status"].eq("complete"), "cafe_size_adjusted_full_score"] = np.nan
    out["cafe_size_adjusted_full_rank"] = _rank_eligible(
        out, "cafe_size_adjusted_full_score", "complete"
    )
    out["cafe_size_adjusted_supply_only_rank"] = _rank_eligible(
        out, "cafe_size_adjusted_supply_only_score", "supply_only"
    )
    out["cafe_size_adjustment_method"] = "ols_residual_log_store_count"
    out["cafe_size_adjustment_population"] = "accessible_official_786"
    return out


def build_review_queue(
    review_queue: pd.DataFrame,
    poi: pd.DataFrame,
    areas: gpd.GeoDataFrame,
    euclidean_radius_m: float = 400,
) -> pd.DataFrame:
    """Attach coordinates and legacy spatial scope to a candidate review queue."""
    required_queue = {"place_id", "place_name", "source_dataset"}
    required_poi = {"place_id", "longitude", "latitude"}
    for label, frame, required in [
        ("review queue", review_queue, required_queue),
        ("POI metadata", poi, required_poi),
    ]:
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} missing columns: {', '.join(missing)}")
    if "area_code" not in areas.columns or "area_name" not in areas.columns:
        raise ValueError("areas must include area_code and area_name")

    queue = review_queue.copy()
    metadata = poi.copy()
    queue["place_id"] = queue["place_id"].astype(str)
    metadata["place_id"] = metadata["place_id"].astype(str)
    metadata = metadata.drop_duplicates("place_id")
    out = queue.merge(metadata, on="place_id", how="left", validate="one_to_one", suffixes=("", "_source"))
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out = out.dropna(subset=["longitude", "latitude"]).copy()

    area_frame = areas[["area_code", "area_name", "geometry"]].copy()
    area_frame["area_code"] = area_frame["area_code"].astype(str)
    points = gpd.GeoDataFrame(
        out,
        geometry=gpd.points_from_xy(out["longitude"], out["latitude"]),
        crs="EPSG:4326",
    ).to_crs("EPSG:5186")
    area_metric = area_frame.to_crs("EPSG:5186").reset_index(drop=True)
    buffered = area_metric.copy()
    buffered["geometry"] = buffered.geometry.buffer(euclidean_radius_m)
    matches = gpd.sjoin(
        points[["place_id", "geometry"]],
        buffered[["area_code", "area_name", "geometry"]],
        how="inner",
        predicate="within",
    )
    if matches.empty:
        return pd.DataFrame(columns=[*out.columns, "matched_area_codes"])

    geometry_by_index = area_metric.geometry.to_dict()
    area_code_by_index = area_metric["area_code"].to_dict()
    area_name_by_index = area_metric["area_name"].to_dict()
    match_rows: list[dict[str, object]] = []
    for place_id, group in matches.groupby("place_id", sort=True):
        point = group.geometry.iloc[0]
        candidates = []
        for index_right in group["index_right"].tolist():
            distance = float(point.distance(geometry_by_index[index_right]))
            candidates.append((distance, area_code_by_index[index_right], area_name_by_index[index_right]))
        candidates.sort(key=lambda item: (item[0], item[1]))
        match_rows.append(
            {
                "place_id": place_id,
                "matched_area_codes": "|".join(item[1] for item in candidates),
                "matched_area_names": "|".join(item[2] for item in candidates),
                "matched_area_code_count": len(candidates),
                "nearest_area_code": candidates[0][1],
                "nearest_area_name": candidates[0][2],
                "euclidean_legacy_distance_m": round(candidates[0][0], 3),
                "inside_official_area": candidates[0][0] == 0.0,
                "included_in_current_786_scope": True,
                "scope_status": "inside_official_area" if candidates[0][0] == 0.0 else "euclidean_buffer_only_pending_walk_network",
            }
        )
    result = out.merge(pd.DataFrame(match_rows), on="place_id", how="inner", validate="one_to_one")
    result["walk_distance_m"] = np.nan
    result["walk_access_status"] = "pending_walk_network"
    result["review_status"] = "pending_evidence_review"
    return result.sort_values(["scope_status", "place_name", "place_id"]).reset_index(drop=True)


def _candidate_metadata(kakao: pd.DataFrame, facilities: pd.DataFrame) -> pd.DataFrame:
    kakao = kakao.copy()
    kakao["place_id"] = kakao["place_id"].astype(str)
    kakao = kakao[["place_id", "longitude", "latitude", "category_name", "road_address_name"]]
    facilities = facilities.copy()
    facilities["place_id"] = facilities["place_id"].astype(str)
    facilities = facilities.loc[facilities["facility_type"].eq("large_cafe")].copy()
    facilities["category_name"] = "OSM large_cafe"
    facilities["road_address_name"] = facilities["address"]
    facilities = facilities[["place_id", "longitude", "latitude", "category_name", "road_address_name"]]
    return pd.concat([kakao, facilities], ignore_index=True).drop_duplicates("place_id")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--review-queue",
        default="data/processed/cafe_study_v1/c_stay_s4_evidence_review_20260929_input.csv",
    )
    parser.add_argument(
        "--draft",
        default="data/processed/cafe_study_v1/cafe_study_score_draft_20260929_input.csv",
    )
    parser.add_argument("--kakao", default="data/external/kakao_study_stay_pois_20260918.csv")
    parser.add_argument("--facilities", default="data/external/study_public_facility_poi.csv")
    parser.add_argument("--areas", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    parser.add_argument("--output-dir", default="data/processed/cafe_study_v1")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    queue = pd.read_csv(args.review_queue, dtype={"place_id": str})
    kakao = pd.read_csv(args.kakao, dtype={"place_id": str})
    facilities = pd.read_csv(args.facilities, dtype={"place_id": str})
    areas = gpd.read_file(args.areas)
    review = build_review_queue(queue, _candidate_metadata(kakao, facilities), areas)
    review.to_csv(output_dir / "c_stay_s4_review_queue_786_euclidean_legacy.csv", index=False, encoding="utf-8-sig")

    draft = pd.read_csv(args.draft, dtype={"area_code": str})
    score = add_size_adjusted_scores(draft)
    score.to_csv(output_dir / "cafe_size_adjusted_score_draft_786.csv", index=False, encoding="utf-8-sig")
    summary = {
        "review_queue_input_rows": int(len(queue)),
        "review_queue_spatially_matched_rows": int(len(review)),
        "review_queue_inside_rows": int(review["inside_official_area"].sum()) if len(review) else 0,
        "review_queue_buffer_only_rows": int((~review["inside_official_area"]).sum()) if len(review) else 0,
        "complete_eligible_size_adjusted_scores": int(score["cafe_size_adjusted_full_rank"].notna().sum()),
        "supply_only_eligible_size_adjusted_scores": int(score["cafe_size_adjusted_supply_only_rank"].notna().sum()),
    }
    (output_dir / "cafe_study_followup_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
