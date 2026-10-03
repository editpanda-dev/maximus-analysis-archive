"""Prepare auditable October 6 preview tables without claiming a verified v1 score."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data/processed/cafe_study_taxonomy"
OUT = IN / "oct06_readiness"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(IN / "cafe_study_score_draft_786.csv", dtype={"area_code": str})
    original = pd.read_csv(
        ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv",
        dtype={"area_code": str},
    )
    assert len(frame) == frame.area_code.nunique() == 786
    assert set(frame.area_code) == set(original.area_code)

    frame["cafe_v1_status"] = np.where(frame.score_status.eq("complete"),
                                       "complete_official_sales_preview", frame.score_status)
    frame["study_v1_status"] = "incomplete_stay_and_walk_evidence"
    frame["walk_network_status"] = "not_computed"
    frame["study_legacy_proxy_rank"] = frame.study_legacy_proxy_score.rank(
        method="min", ascending=False)
    frame["cafe_complete_rank"] = np.nan
    ranked = frame.score_status.eq("complete") & frame.recommendation_eligible
    frame.loc[ranked, "cafe_complete_rank"] = frame.loc[ranked, "full_score"].rank(
        method="min", ascending=False)
    frame["coffee_subtype_score"] = frame.coffee_full_score
    frame["bakery_subtype_score"] = frame.bakery_full_score
    frame["study_cafe_subtype_proxy"] = frame.study_cafe_percentile
    frame["study_room_subtype_proxy"] = frame.study_room_percentile
    frame["study_public_subtype_proxy"] = frame.study_public_percentile
    frame["subtype_top3_status"] = "incomplete_S4_and_unverified_public_access"
    selected = ["area_code", "area_name", "area_type_name", "analysis_universe",
                "recommendation_eligible", "exclusion_reason", "score_status", "cafe_v1_status",
                "full_score", "supply_only_score", "cafe_complete_rank", "coffee_subtype_score",
                "bakery_subtype_score", "coffee_stores", "bakery_stores", "coffee_sales_observed",
                "bakery_sales_observed", "study_v1_score", "study_v1_status",
                "study_legacy_proxy_score", "study_legacy_proxy_rank", "study_cafe_subtype_proxy",
                "study_room_subtype_proxy", "study_public_subtype_proxy", "subtype_top3_status",
                "walk_network_status", "minimum_period_ratio", "score_basis"]
    frame[selected].sort_values("area_code").to_csv(
        OUT / "cafe_study_scorecard_readiness_786.csv", index=False, encoding="utf-8-sig")

    cafe = frame.loc[ranked].sort_values(["full_score", "area_code"], ascending=[False, True]).head(20).copy()
    cafe.insert(0, "preview_rank", np.arange(1, len(cafe) + 1))
    cafe["evidence_sentence"] = ("커피·음료 점포 " + cafe.coffee_stores.astype(int).astype(str)
                                 + "개, 제과점 " + cafe.bakery_stores.astype(int).astype(str)
                                 + "개; 두 업종 추정매출 관측. 보행·착석 여부 미반영")
    cafe[["preview_rank", "area_code", "area_name", "full_score", "coffee_subtype_score",
          "bakery_subtype_score", "coffee_stores", "bakery_stores", "evidence_sentence"]].to_csv(
        OUT / "cafe_top20_complete_preview.csv", index=False, encoding="utf-8-sig")

    study = frame.loc[frame.recommendation_eligible].sort_values(
        ["study_legacy_proxy_score", "area_code"], ascending=[False, True]).head(20).copy()
    study.insert(0, "preview_rank", np.arange(1, len(study) + 1))
    study["evidence_sentence"] = ("기존 공부 체류 프록시 "
                                  + study.study_legacy_proxy_score.round(1).astype(str)
                                  + "점; S4 체류 확인·보행거리 미완료")
    study[["preview_rank", "area_code", "area_name", "study_legacy_proxy_score",
           "study_cafe_inside_count", "study_room_stores", "study_public_inside_count",
           "evidence_sentence"]].to_csv(
        OUT / "study_top20_legacy_proxy_preview.csv", index=False, encoding="utf-8-sig")

    # Both percentiles have the same observed cafe-sales subset as denominator.
    combo = frame.loc[ranked].copy()
    combo["cafe_percentile_common_universe"] = combo.full_score.rank(method="average", pct=True) * 100
    combo["study_proxy_percentile_common_universe"] = combo.study_legacy_proxy_score.rank(
        method="average", pct=True) * 100
    combo["cafe_study_preview_score"] = .5 * (
        combo.cafe_percentile_common_universe + combo.study_proxy_percentile_common_universe)
    combo = combo.sort_values(["cafe_study_preview_score", "area_code"], ascending=[False, True])
    combo.insert(0, "preview_rank", np.arange(1, len(combo) + 1))
    combo["status"] = "exploratory_same_observed_subset_not_final_v1"
    combo.head(20)[["preview_rank", "area_code", "area_name", "cafe_study_preview_score",
                    "cafe_percentile_common_universe", "study_proxy_percentile_common_universe",
                    "status"]].to_csv(OUT / "cafe_study_top20_exploratory.csv", index=False, encoding="utf-8-sig")

    # GIS-ready layer; ranks are marked as previews in every exported feature.
    geo_path = ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"
    layer = json.loads(geo_path.read_text(encoding="utf-8"))
    cafe_ranks = dict(zip(cafe.area_code, cafe.preview_rank))
    study_ranks = dict(zip(study.area_code, study.preview_rank))
    combo_ranks = dict(zip(combo.head(20).area_code, combo.head(20).preview_rank))
    for feature in layer["features"]:
        code = str(feature["properties"]["area_code"])
        feature["properties"] = {"area_code": code,
                                  "area_name": feature["properties"].get("area_name", ""),
                                  "cafe_preview_top20_rank": cafe_ranks.get(code),
                                  "study_legacy_top20_rank": study_ranks.get(code),
                                  "cafe_study_exploratory_top20_rank": combo_ranks.get(code),
                                  "map_status": "preview_not_walk_or_verified_study_v1"}
    (OUT / "cafe_study_top20_preview_map.geojson").write_text(
        json.dumps(layer, ensure_ascii=False), encoding="utf-8")

    qa = pd.DataFrame([
        ("area_rows", "PASS", len(frame), "786"),
        ("unique_area_code", "PASS" if frame.area_code.is_unique else "FAIL", frame.area_code.nunique(), "786"),
        ("candidate_code_set", "PASS" if set(frame.area_code) == set(original.area_code) else "FAIL",
         len(set(frame.area_code) & set(original.area_code)), "786"),
        ("complete_cafe_sales", "PASS", int(frame.score_status.eq("complete").sum()), "observed subset only"),
        ("noncomplete_full_score_null", "PASS" if frame.loc[~ranked & frame.recommendation_eligible,
                                                              "full_score"].isna().all() else "FAIL",
         int(frame.loc[frame.score_status.ne("complete"), "full_score"].notna().sum()), "0"),
        ("study_v1_unverified_null", "PASS" if frame.study_v1_score.isna().all() else "FAIL",
         int(frame.study_v1_score.notna().sum()), "0"),
        ("scores_in_0_100", "PASS" if frame.full_score.dropna().between(0, 100).all() else "FAIL",
         int(frame.full_score.notna().sum()), "all observed"),
        ("tourism_reference_only", "PASS" if frame.loc[frame.area_type_name.eq("관광특구"),
                                                        "recommendation_eligible"].eq(False).all() else "FAIL",
         int(frame.area_type_name.eq("관광특구").sum()), "exclude from preview ranks"),
        ("walk_routes", "BLOCKED_INPUT", 0, "pedestrian graph and entrance links needed"),
        ("S4_verified", "BLOCKED_EVIDENCE", 0, "verified study permission needed"),
    ], columns=["check", "status", "observed", "expected_or_note"])
    qa.to_csv(OUT / "oct06_readiness_qa.csv", index=False, encoding="utf-8-sig")
    if qa.status.eq("FAIL").any():
        raise AssertionError(qa.loc[qa.status.eq("FAIL")].to_string(index=False))
    print(qa.to_string(index=False))


if __name__ == "__main__":
    main()
