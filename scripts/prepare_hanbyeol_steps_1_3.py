"""Versioned cafe/study classification, duplicate-signal, and evidence audits.

These audits do not replace PATH-v0 or claim a verified study score.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyze_hanbyeol_cafe_study_v1_draft import read_zip_csv


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/cafe_study_taxonomy/steps_1_3"
BAKERY = "CS100005"
COFFEE = "CS100010"
STUDY_ROOM = "CS200038"


def classify_v1(code: str, legacy_purpose: str | None) -> str | None:
    """Move one exact official code; leave all other legacy mappings untouched."""
    return "카페" if code == BAKERY else legacy_purpose


def validate_review(frame: pd.DataFrame) -> pd.DataFrame:
    """Return row-level status; unknown means unreviewed, never a negative finding."""
    required = ["place_id", "place_name", "evidence_source_url", "evidence_quote",
                "seat_verified", "study_allowed_verified", "mandatory_purchase",
                "reviewer", "reviewed_at", "decision"]
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing evidence fields: {sorted(missing)}")
    result = frame.copy()
    valid_tri = {"yes", "no", "unknown"}
    valid_decisions = {"unknown", "c_stay_verified", "s4_verified", "takeout_verified", "excluded"}
    valid_basis = {"unknown", "long_stay_explicit", "laptop_explicit", "study_explicit",
                   "seat_only_explicit", "takeout_only_explicit", "not_eligible_explicit"}
    for i, row in result.iterrows():
        tri = {str(row[c]).lower() for c in ("seat_verified", "study_allowed_verified", "mandatory_purchase")}
        decision = str(row.decision).lower()
        basis = str(row.get("evidence_type", "unknown")).lower()
        if not tri <= valid_tri or decision not in valid_decisions or basis not in valid_basis:
            status = "invalid_enum"
        elif decision == "unknown":
            status = "pending"
        elif any(pd.isna(row[c]) or str(row[c]).strip() == "" for c in
                 ("evidence_source_url", "evidence_quote", "reviewer", "reviewed_at")):
            status = "missing_evidence_or_reviewer"
        elif decision == "s4_verified" and not (row.seat_verified == "yes" and row.study_allowed_verified == "yes"):
            status = "contradictory_s4"
        elif decision == "c_stay_verified" and row.seat_verified != "yes":
            status = "contradictory_stay"
        elif decision == "takeout_verified" and row.seat_verified != "no":
            status = "contradictory_takeout"
        elif decision == "c_stay_verified" and basis not in {"long_stay_explicit", "laptop_explicit", "study_explicit"}:
            status = "stay_duration_not_supported"
        elif decision == "s4_verified" and basis not in {"long_stay_explicit", "laptop_explicit", "study_explicit"}:
            status = "study_use_not_supported"
        else:
            status = "reviewed"
        result.at[i, "validation_status"] = status
    return result


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = ROOT / "data/raw/commercial_area"
    stores = read_zip_csv(raw / "commercial_store_2025.zip")
    sales = read_zip_csv(raw / "commercial_sales_2025.zip")
    areas = pd.read_csv(ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv",
                        dtype={"area_code": str})[["area_code", "area_name"]]
    assert len(areas) == areas.area_code.nunique() == 786
    store_q = stores.loc[stores.stdr_yyqu_cd.eq(20254)].copy()
    sales_q = sales.loc[sales["기준_년분기_코드"].eq(20254)].copy()
    assert (store_q.loc[store_q.svc_induty_cd.eq(BAKERY), "svc_induty_cd_nm"] == "제과점").all()
    assert (sales_q.loc[sales_q["서비스_업종_코드"].eq(BAKERY), "서비스_업종_코드_명"] == "제과점").all()
    assert not store_q.duplicated(["trdar_cd", "svc_induty_cd"]).any()
    assert not sales_q.duplicated(["상권_코드", "서비스_업종_코드"]).any()

    # This is a versioned audit of the transfer, not a silent PATH-v0 rewrite.
    from scripts.build_purpose_features import map_industry_to_purpose
    mapping = pd.DataFrame([
        {"industry_code": c, "industry_name": n,
         "path_v0_purpose": map_industry_to_purpose(n),
         "cafe_study_v1_purpose": classify_v1(c, map_industry_to_purpose(n))}
        for c, n in store_q[["svc_induty_cd", "svc_induty_cd_nm"]].drop_duplicates().itertuples(index=False, name=None)
    ])
    assert len(mapping.loc[mapping.industry_code.eq(BAKERY)]) == 1
    assert mapping.loc[mapping.industry_code.eq(BAKERY), "path_v0_purpose"].item() == "식사"
    assert mapping.loc[mapping.industry_code.eq(BAKERY), "cafe_study_v1_purpose"].item() == "카페"
    assert (mapping.loc[mapping.industry_code.ne(BAKERY), "path_v0_purpose"].fillna("") ==
            mapping.loc[mapping.industry_code.ne(BAKERY), "cafe_study_v1_purpose"].fillna("")).all()
    mapping["source"] = "Seoul commercial_store_2025.zip / 2025Q4; purpose map in scripts/build_purpose_features.py"
    mapping.to_csv(OUT / "industry_transfer_mapping_v1.csv", index=False, encoding="utf-8-sig")

    def aggregate(df: pd.DataFrame, area_col: str, code_col: str, value_col: str, prefix: str) -> pd.DataFrame:
        active = df[df[area_col].isin(areas.area_code)].copy()
        active = active.merge(mapping[["industry_code", "path_v0_purpose", "cafe_study_v1_purpose"]],
                              left_on=code_col, right_on="industry_code", how="left", validate="many_to_one")
        old = active.pivot_table(index=area_col, columns="path_v0_purpose", values=value_col, aggfunc="sum")
        new = active.pivot_table(index=area_col, columns="cafe_study_v1_purpose", values=value_col, aggfunc="sum")
        bakery = active.loc[active[code_col].eq(BAKERY)].set_index(area_col)[value_col]
        result = areas[["area_code"]].set_index("area_code")
        for purpose in ["식사", "카페"]:
            result[f"path_v0_{purpose}_{prefix}"] = old.get(purpose, pd.Series(dtype=float))
            result[f"v1_{purpose}_{prefix}"] = new.get(purpose, pd.Series(dtype=float))
        result[f"bakery_{prefix}"] = bakery
        result[f"bakery_{prefix}_source_row_observed"] = result.index.isin(bakery.index)
        return result

    store_audit = aggregate(store_q, "trdar_cd", "svc_induty_cd", "stor_co", "stores")
    sales_audit = aggregate(sales_q, "상권_코드", "서비스_업종_코드", "당월_매출_금액", "sales")
    audit = areas.set_index("area_code").join(store_audit).join(sales_audit).reset_index()
    for suffix in ("stores", "sales"):
        subset = audit.loc[audit[f"bakery_{suffix}_source_row_observed"]]
        assert np.allclose(subset[f"path_v0_식사_{suffix}"].fillna(0) - subset[f"v1_식사_{suffix}"].fillna(0),
                           subset[f"bakery_{suffix}"])
        assert np.allclose(subset[f"v1_카페_{suffix}"].fillna(0) - subset[f"path_v0_카페_{suffix}"].fillna(0),
                           subset[f"bakery_{suffix}"])
    audit["definition_version"] = "cafe_study_v1_transfer_proposal_2026-10-03"
    audit["sales_missing_rule"] = "missing_source_row_is_unknown_not_zero"
    audit.to_csv(OUT / "bakery_transfer_area_audit_786.csv", index=False, encoding="utf-8-sig")

    comparison = pd.read_csv(ROOT / "data/processed/cafe_study_taxonomy/s3a_s3b_proxy_comparison_786.csv",
                             dtype={"area_code": str})
    assert len(comparison) == comparison.area_code.nunique() == 786
    comparison["v1_s3a_role"] = "primary_supply_proxy_unverified_poi"
    comparison["v1_s3b_role"] = "validation_column_only_not_added_to_s3a"
    comparison["unique_facility_count_available"] = False
    comparison["study_v1_score"] = np.nan
    comparison["v1_status"] = "incomplete_stay_evidence"
    comparison.to_csv(OUT / "s3_primary_and_validation_786.csv", index=False, encoding="utf-8-sig")

    queue = pd.read_csv(ROOT / "data/processed/cafe_study_taxonomy/c_stay_s4_evidence_review.csv",
                        dtype={"place_id": str}).fillna("")
    assert len(queue) == 427
    kakao = queue.source_dataset.str.startswith("kakao_")
    queue.loc[kakao, "candidate_source_url"] = "https://place.map.kakao.com/" + queue.loc[kakao, "place_id"]
    kakao_raw = pd.read_csv(ROOT / "data/external/kakao_study_stay_pois_20260918.csv",
                            dtype={"place_id": str}).set_index("place_id")
    queue["source_address_name"] = ""
    queue.loc[kakao, "source_address_name"] = queue.loc[kakao, "place_id"].map(kakao_raw.address_name).fillna("")
    queue["address_in_seoul"] = np.where(kakao, queue.source_address_name.str.startswith("서울"), pd.NA)
    queue["candidate_url_is_evidence"] = False
    queue["review_scope"] = "candidate_unverified_location_and_operation"
    queue["evidence_type"] = "unknown"
    queue = validate_review(queue)
    assert queue.validation_status.eq("pending").all()
    assert queue.decision.eq("unknown").all()
    queue.to_csv(OUT / "c_stay_s4_review_queue_v1.csv", index=False, encoding="utf-8-sig")

    checks = {
        "area_rows": len(audit), "unique_area_codes": audit.area_code.nunique(),
        "bakery_store_rows_2025q4_in_786": int(audit.bakery_stores_source_row_observed.sum()),
        "bakery_sales_rows_2025q4_in_786": int(audit.bakery_sales_source_row_observed.sum()),
        "s3a_s3b_area_rows": len(comparison),
        "review_queue_rows": len(queue), "reviewed_evidence_rows": int(queue.validation_status.eq("reviewed").sum()),
        "unknown_review_rows": int(queue.decision.eq("unknown").sum()),
        "study_v1_scored_rows": int(comparison.study_v1_score.notna().sum()),
    }
    pd.DataFrame([{"check": k, "value": v} for k, v in checks.items()]).to_csv(
        OUT / "steps_1_3_counts_qa.csv", index=False, encoding="utf-8-sig")
    print(checks)


if __name__ == "__main__":
    build()
