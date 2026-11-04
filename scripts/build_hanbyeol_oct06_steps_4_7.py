"""Generate an explicitly partial Oct 6 handoff from observed source data.

No route length, verified S4 count, or final study score is imputed here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/cafe_study_taxonomy"
OUT = SOURCE / "oct06_steps_4_7"


def stable_top(frame: pd.DataFrame, score: str, count: int) -> pd.DataFrame:
    ranked = frame.sort_values([score, "area_code"], ascending=[False, True]).head(count).copy()
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(SOURCE / "cafe_study_score_draft_786.csv", dtype={"area_code": str})
    correction = pd.read_csv(SOURCE / "cafe_size_correction_786.csv", dtype={"area_code": str})
    transfer = pd.read_csv(SOURCE / "steps_1_3/cross_purpose_transfer_area_audit_786.csv",
                           dtype={"area_code": str})
    review = pd.read_csv(SOURCE / "steps_1_3/c_stay_s4_review_queue_v1.csv", dtype={"place_id": str})
    candidate = pd.read_csv(ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv",
                            dtype={"area_code": str})
    for source in (raw, correction, transfer, candidate):
        assert len(source) == source.area_code.nunique() == 786
    assert set(raw.area_code) == set(candidate.area_code) == set(transfer.area_code)

    frame = raw.merge(correction[["area_code", "density", "industry_lq", "residual_log_count",
                                   "ranking_evidence_eligible"]], on="area_code", validate="one_to_one")
    frame = frame.merge(transfer[["area_code", "bakery_stores", "bakery_sales_source_row_observed",
                                  "bar_stores"]].rename(columns={"bakery_stores": "bakery_stores_audit"}),
                        on="area_code", validate="one_to_one")
    assert np.allclose(frame.bakery_stores, frame.bakery_stores_audit.fillna(0))
    assert (frame.bakery_sales_observed == frame.bakery_sales_source_row_observed).all()

    # Residual correction remains an alternative, not an unannounced replacement
    # for the recorded cafe score. Eligibility avoids one-shop relative outliers.
    valid_residual = frame.ranking_evidence_eligible
    frame["cafe_size_residual_percentile_exploratory"] = np.nan
    frame.loc[valid_residual, "cafe_size_residual_percentile_exploratory"] = (
        frame.loc[valid_residual, "residual_log_count"].rank(method="average", pct=True) * 100)
    frame["cafe_size_method_status"] = np.where(valid_residual,
                                                  "residual_candidate_min10_cafe_min50_total",
                                                  "below_residual_ranking_support")
    frame["cafe_full_score"] = frame.full_score.where(frame.score_status.eq("complete"))
    frame["cafe_supply_only_score"] = frame.supply_only_score.where(frame.score_status.eq("supply_only"))
    # Diagnostic only: exchange the combined supply block for the size residual.
    # Consumption is algebraically extracted from the recorded full score on
    # rows where both source industries have disclosed sales.
    observed_consumption = (frame.full_score - .70 * frame.supply_only_score) / .30
    residual_base = valid_residual & frame.score_status.eq("complete")
    frame["cafe_residual_variant_score"] = (
        .70 * frame.cafe_size_residual_percentile_exploratory + .30 * observed_consumption
    ).where(residual_base)
    frame["study_final_score"] = np.nan
    frame["study_final_status"] = "incomplete_stay_evidence_and_walk_network"
    frame["walk_network_status"] = "not_computed_missing_graph_and_runtime"
    frame["verified_c_stay_count"] = np.nan
    frame["verified_s4_count"] = np.nan
    frame["study_s3a_input_role"] = "primary_unverified_candidate"
    frame["study_s3b_input_role"] = "validation_only_not_added"
    frame["cafe_subtype_best"] = np.where(
        frame.coffee_full_score.notna() & frame.bakery_full_score.notna(),
        np.where(frame.coffee_full_score >= frame.bakery_full_score, "C1_coffee", "C2_bakery"), "unknown")
    frame["cafe_top3_status"] = "only_C1_C2_scored_C_stay_unverified"
    frame["analysis_universe"] = "accessible_official_786"
    frame["recommendation_universe"] = np.where(frame.recommendation_eligible,
                                                  "non_tourism_observed_subset_if_ranked", "broad_tourism_reference")
    frame["score_version"] = "cafe_draft_2025q4_observed_sales_study_unverified_2026poi"
    cols = ["area_code", "area_name", "area_type_name", "analysis_universe", "recommendation_universe",
            "recommendation_eligible", "exclusion_reason", "coffee_stores", "bakery_stores", "bar_stores",
            "coffee_sales_observed", "bakery_sales_observed", "score_status", "score_status_reason",
            "coffee_supply_score", "bakery_supply_score", "coffee_full_score", "bakery_full_score",
            "cafe_full_score", "cafe_supply_only_score", "cafe_subtype_best", "cafe_top3_status",
            "area_km2", "total_stores_2025q4", "density", "industry_lq", "residual_log_count",
            "cafe_size_residual_percentile_exploratory", "cafe_size_method_status",
            "cafe_residual_variant_score",
            "study_cafe_inside_count", "study_room_stores", "study_public_inside_count",
            "study_public_nearby_only_count", "study_s3a_input_role", "study_s3b_input_role",
            "verified_c_stay_count", "verified_s4_count", "study_final_score", "study_final_status",
            "study_legacy_proxy_score", "walk_network_status", "score_version"]
    frame[cols].sort_values("area_code").to_csv(OUT / "cafe_study_v1_handoff_786.csv", index=False,
                                              encoding="utf-8-sig")

    eligible = frame[frame.recommendation_eligible & frame.score_status.eq("complete")].copy()
    top20 = stable_top(eligible, "cafe_full_score", 20)
    top20["evidence_sentence"] = ("2025Q4 커피·음료 점포 " + top20.coffee_stores.astype(int).astype(str)
        + "개와 제과점 " + top20.bakery_stores.astype(int).astype(str)
        + "개; 두 업종 매출 공개. 체류·보행은 검증 전")
    top20[["rank", "area_code", "area_name", "cafe_full_score", "coffee_supply_score",
           "bakery_supply_score", "coffee_full_score", "bakery_full_score", "cafe_subtype_best",
           "evidence_sentence"]].to_csv(OUT / "cafe_top20_observed_preview.csv", index=False,
                                         encoding="utf-8-sig")
    top20.head(10).to_csv(OUT / "cafe_top10_observed_preview.csv", index=False, encoding="utf-8-sig")

    study_preview = stable_top(frame.loc[frame.recommendation_eligible], "study_legacy_proxy_score", 20)
    study_preview["ranking_status"] = "legacy_proxy_not_verified_study_v1"
    study_preview["evidence_sentence"] = ("기존 공부 체류 프록시 "
        + study_preview.study_legacy_proxy_score.round(1).astype(str)
        + "점; S3b 중복·S4 이용 근거·보행거리 검증 전")
    study_preview[["rank", "area_code", "area_name", "study_legacy_proxy_score",
                   "study_cafe_inside_count", "study_room_stores", "study_public_inside_count",
                   "ranking_status", "evidence_sentence"]].to_csv(
                       OUT / "study_top20_legacy_proxy_preview.csv", index=False, encoding="utf-8-sig")
    study_preview.head(10).to_csv(OUT / "study_top10_legacy_proxy_preview.csv", index=False,
                                  encoding="utf-8-sig")

    # A conditional comparison among the same eligible/observed areas.
    eligible["cafe_percentile_on_complete_subset"] = eligible.cafe_full_score.rank(method="average", pct=True) * 100
    eligible["study_legacy_percentile_on_complete_subset"] = eligible.study_legacy_proxy_score.rank(
        method="average", pct=True) * 100
    eligible["combo_exploratory_score"] = (eligible.cafe_percentile_on_complete_subset
                                           + eligible.study_legacy_percentile_on_complete_subset) / 2
    combo = stable_top(eligible, "combo_exploratory_score", 20)
    combo["ranking_status"] = "legacy_study_proxy_exploratory_not_final_v1"
    combo[["rank", "area_code", "area_name", "combo_exploratory_score",
           "cafe_percentile_on_complete_subset", "study_legacy_percentile_on_complete_subset",
           "ranking_status"]].to_csv(OUT / "cafe_study_top20_exploratory.csv", index=False,
                                     encoding="utf-8-sig")
    combo.head(10).to_csv(OUT / "cafe_study_top10_exploratory.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"combination": "meal+cafe+study", "top10_status": "not_computed",
                   "reason": "team_common_meal_mapping_and_verified_study_score_unavailable"}]).to_csv(
                       OUT / "three_purpose_top10_status.csv", index=False, encoding="utf-8-sig")

    # Keep map provenance on each polygon rather than implying walking access.
    geo_path = ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"
    layer = json.loads(geo_path.read_text(encoding="utf-8"))
    ranks = dict(zip(top20.area_code, top20["rank"]))
    study_ranks = dict(zip(study_preview.area_code, study_preview["rank"]))
    combo_ranks = dict(zip(combo.area_code, combo["rank"]))
    status = frame.set_index("area_code").score_status.to_dict()
    for feature in layer["features"]:
        code = str(feature["properties"]["area_code"])
        feature["properties"] = {"area_code": code, "area_name": feature["properties"].get("area_name"),
                                  "cafe_top20_observed_rank": ranks.get(code),
                                  "study_legacy_top20_rank": study_ranks.get(code),
                                  "cafe_study_exploratory_rank": combo_ranks.get(code),
                                  "cafe_sales_status": status[code],
                                  "map_status": "preview_no_verified_walk_or_study_score"}
    (OUT / "cafe_study_preview_map_786.geojson").write_text(json.dumps(layer, ensure_ascii=False), encoding="utf-8")

    size_summary = pd.read_csv(SOURCE / "cafe_size_correction_summary.csv")
    adj_summary = pd.read_csv(SOURCE / "adjacency_weight_euclidean_legacy_summary.csv")
    size_summary.to_csv(OUT / "cafe_size_four_methods_comparison.csv", index=False, encoding="utf-8-sig")
    adj_summary.to_csv(OUT / "public_adjacency_euclidean_legacy_only.csv", index=False, encoding="utf-8-sig")
    same = frame.loc[residual_base & frame.recommendation_eligible]
    original_top = set(stable_top(same, "cafe_full_score", 10).area_code)
    residual_top = set(stable_top(same, "cafe_residual_variant_score", 10).area_code)
    pd.DataFrame([{"variant": "recorded_cafe_full_on_common_subset",
                   "common_observed_eligible_areas": len(same),
                   "area_spearman": same.cafe_full_score.corr(same.area_km2, method="spearman"),
                   "top10_overlap_vs_recorded": 1.0},
                  {"variant": "residual_supply_70pct_observed_consumption_30pct_exploratory",
                   "common_observed_eligible_areas": len(same),
                   "area_spearman": same.cafe_residual_variant_score.corr(same.area_km2, method="spearman"),
                   "top10_overlap_vs_recorded": len(original_top & residual_top) / 10}]).to_csv(
                       OUT / "cafe_residual_score_variant_comparison.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"radius_m": r, "status": "blocked_missing_pedestrian_network",
                   "eligible_area_count": np.nan, "top10_overlap_vs_400": np.nan,
                   "rank_spearman_vs_400": np.nan, "walk_network_source": "unavailable"}
                  for r in (400, 500, 600)]).to_csv(OUT / "walk_radius_400_500_600_status.csv", index=False,
                                                    encoding="utf-8-sig")

    checks = [
        ("area_rows_and_unique_code", len(frame) == frame.area_code.nunique() == 786, len(frame), "786"),
        ("area_code_matches_source", set(frame.area_code) == set(candidate.area_code), len(set(frame.area_code) & set(candidate.area_code)), "786"),
        ("cafe_complete_only_observed", frame.loc[frame.score_status.ne("complete"), "cafe_full_score"].isna().all(), int(frame.cafe_full_score.notna().sum()), "224 complete"),
        ("cafe_supply_only_rank_separate", frame.loc[frame.score_status.ne("supply_only"), "cafe_supply_only_score"].isna().all(), int(frame.cafe_supply_only_score.notna().sum()), "232 supply_only"),
        ("cafe_full_score_range", frame.cafe_full_score.dropna().between(0, 100).all(), int(frame.cafe_full_score.notna().sum()), "0..100"),
        ("residual_variant_observed_only", frame.loc[~residual_base, "cafe_residual_variant_score"].isna().all() and frame.cafe_residual_variant_score.dropna().between(0,100).all(), int(frame.cafe_residual_variant_score.notna().sum()), "qualified observed only, 0..100"),
        ("study_unverified_null", frame.study_final_score.isna().all(), int(frame.study_final_score.notna().sum()), "0"),
        ("s4_unverified_null", frame.verified_s4_count.isna().all() and review.decision.eq("unknown").all(), int(review.decision.ne("unknown").sum()), "0"),
        ("broad_tourism_excluded_from_rank", not top20.area_code.isin(frame.loc[~frame.recommendation_eligible, "area_code"]).any(), int((~frame.recommendation_eligible).sum()), "6 reference polygons"),
        ("top20_complete_only", top20.score_status.eq("complete").all() and len(top20) == 20, len(top20), "20"),
        ("map_786_features", len(layer["features"]) == 786, len(layer["features"]), "786"),
    ]
    qa = pd.DataFrame([{"check": name, "status": "PASS" if ok else "FAIL", "observed": observed,
                        "expected": expected} for name, ok, observed, expected in checks])
    qa = pd.concat([qa, pd.DataFrame([
        {"check": "network_radius_400_500_600", "status": "BLOCKED_INPUT", "observed": 0,
         "expected": "real legal pedestrian graph and entrance connectors"},
        {"check": "verified_c_stay_s4", "status": "BLOCKED_EVIDENCE", "observed": 0,
         "expected": "source quote plus reviewer for each accepted POI"},
        {"check": "meal_cafe_study_top10", "status": "BLOCKED_INTEGRATION", "observed": 0,
         "expected": "team-common purpose v1 and study final score"},
    ])], ignore_index=True)
    qa.to_csv(OUT / "oct06_steps_4_7_qa.csv", index=False, encoding="utf-8-sig")
    if qa.status.eq("FAIL").any():
        raise AssertionError(qa.loc[qa.status.eq("FAIL")].to_string(index=False))
    print(qa.to_string(index=False))


if __name__ == "__main__":
    build()
