"""Auditable cafe/study taxonomy diagnostics from existing repository snapshots.

This does not manufacture a walk-network distance or a verified cafe-study score.
"""

from __future__ import annotations

import io
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/cafe_study_taxonomy"
CODE_COFFEE = "CS100010"
CODE_BAKERY = "CS100005"
CODE_STUDY_ROOM = "CS200038"


def read_zip_csv(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"Expected one CSV member in {path}")
        return pd.read_csv(io.BytesIO(archive.read(members[0])), encoding="cp949",
                           dtype={"trdar_cd": str, "상권_코드": str,
                                  "svc_induty_cd": str, "서비스_업종_코드": str})


def positive_pct(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").clip(lower=0)
    result = pd.Series(0.0, index=x.index)
    positives = x.gt(0)
    if positives.any() and x.loc[positives].nunique() > 1:
        result.loc[positives] = x.loc[positives].rank(method="average", pct=True) * 100
    return result


def names_top(frame: pd.DataFrame, column: str, k: int = 10) -> list[str]:
    return frame.sort_values([column, "area_code"], ascending=[False, True]).head(k).area_code.tolist()


def overlap(a: list[str], b: list[str]) -> float:
    return len(set(a) & set(b)) / min(len(a), len(b)) if a and b else np.nan


def safe_spearman(a: pd.Series, b: pd.Series) -> float:
    mask = a.notna() & b.notna()
    if mask.sum() < 3 or a[mask].nunique() < 2 or b[mask].nunique() < 2:
        return np.nan
    return float(spearmanr(a[mask], b[mask]).statistic)


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_csv(ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv",
                             dtype={"area_code": str})
    study = pd.read_csv(ROOT / "data/processed/study_stay_poi_enrichment/official_area_study_stay_enriched_current.csv",
                        dtype={"area_code": str})
    public = pd.read_csv(ROOT / "data/processed/study_public_facility_features.csv", dtype={"area_code": str})
    pois = pd.read_csv(ROOT / "data/external/study_public_facility_poi.csv", dtype={"place_id": str})
    kakao = pd.read_csv(ROOT / "data/external/kakao_study_stay_pois_20260918.csv", dtype={"place_id": str})
    stores = read_zip_csv(ROOT / "data/raw/commercial_area/commercial_store_2025.zip")
    sales = read_zip_csv(ROOT / "data/raw/commercial_area/commercial_sales_2025.zip")
    assert candidates.area_code.nunique() == len(candidates) == 786
    assert len(study) == len(public) == 786 and len(pois) == 268
    stores = stores.loc[stores.stdr_yyqu_cd.eq(20254)].copy()
    sales = sales.loc[sales["기준_년분기_코드"].eq(20254)].copy()
    for code, name in [(CODE_COFFEE, "커피-음료"), (CODE_BAKERY, "제과점"), (CODE_STUDY_ROOM, "독서실")]:
        assert (stores.loc[stores.svc_induty_cd.eq(code), "svc_induty_cd_nm"] == name).all()
    for code, name in [(CODE_COFFEE, "커피-음료"), (CODE_BAKERY, "제과점")]:
        assert (sales.loc[sales["서비스_업종_코드"].eq(code), "서비스_업종_코드_명"] == name).all()

    frame = candidates[["area_code", "area_name", "area_type_name", "minimum_period_ratio"]].copy()
    frame = frame.merge(study[["area_code", "area_km2", "study_cafe_inside_count", "study_room_store_count",
                               "study_cafe_percentile", "study_room_percentile", "cafe_supply_percentile",
                               "starbucks_percentile", "study_public_percentile", "access_percentile",
                               "study_stay_current_score"]], on="area_code", validate="one_to_one")
    frame = frame.merge(public[["area_code", "study_public_inside_count", "study_public_nearby_only_count"]],
                        on="area_code", validate="one_to_one")
    total = stores.groupby("trdar_cd").stor_co.sum().rename("total_stores_2025q4")
    by_code = stores[stores.svc_induty_cd.isin([CODE_COFFEE, CODE_BAKERY, CODE_STUDY_ROOM])].pivot_table(
        index="trdar_cd", columns="svc_induty_cd", values="stor_co", aggfunc="sum", fill_value=0)
    by_code = by_code.reindex(columns=[CODE_COFFEE, CODE_BAKERY, CODE_STUDY_ROOM], fill_value=0)
    by_code.columns = ["coffee_stores", "bakery_stores", "study_room_stores"]
    frame = frame.join(total, on="area_code").join(by_code, on="area_code")
    for col in ["total_stores_2025q4", "coffee_stores", "bakery_stores", "study_room_stores"]:
        frame[col] = frame[col].fillna(0)
    frame["cafe_stores"] = frame.coffee_stores + frame.bakery_stores

    # Keep broad tourism polygons for analysis and label the recommendation filter.
    frame["recommendation_eligible"] = frame.area_type_name.ne("관광특구")
    frame["exclusion_reason"] = np.where(frame.recommendation_eligible, "", "broad_tourism_zone;prefer_named_subarea")
    frame["analysis_universe"] = "accessible_official_786"
    frame["recommendation_universe"] = np.where(frame.recommendation_eligible,
                                                   "named_subarea_candidate", "broad_zone_reference_only")

    # Revenue observation is determined by actual source row presence, never from filled PATH-v0 zeros.
    sales_cafe = sales[sales["서비스_업종_코드"].isin([CODE_COFFEE, CODE_BAKERY])].copy()
    if sales_cafe.duplicated(["상권_코드", "서비스_업종_코드"]).any():
        raise ValueError("Duplicate area-industry sales rows require source audit")
    market_sales = sales.groupby("상권_코드")["당월_매출_금액"].sum().rename("disclosed_market_sales")
    frame = frame.join(market_sales, on="area_code")
    for code, prefix, store_col in [(CODE_COFFEE, "coffee", "coffee_stores"),
                                    (CODE_BAKERY, "bakery", "bakery_stores")]:
        subset = sales_cafe.loc[sales_cafe["서비스_업종_코드"].eq(code)].set_index("상권_코드")
        frame[f"{prefix}_sales_observed"] = frame.area_code.isin(subset.index)
        for source, target in [("당월_매출_금액", "sales_amount"),
                               ("시간대_11~14_매출_금액", "lunch_sales"),
                               ("시간대_14~17_매출_금액", "afternoon_sales")]:
            frame[f"{prefix}_{target}"] = frame.area_code.map(subset[source])
        frame[f"{prefix}_store_share"] = frame[store_col] / frame.total_stores_2025q4.replace(0, np.nan)
        frame[f"{prefix}_sales_share"] = frame[f"{prefix}_sales_amount"] / frame.disclosed_market_sales.replace(0, np.nan)
        frame[f"{prefix}_time_share"] = (
            frame[f"{prefix}_lunch_sales"] + frame[f"{prefix}_afternoon_sales"]
        ) / frame[f"{prefix}_sales_amount"].replace(0, np.nan)
        supply_parts = [positive_pct(frame[store_col] / frame.area_km2.clip(lower=0.02)),
                        positive_pct(frame[f"{prefix}_store_share"])]
        frame[f"{prefix}_supply_score"] = 0.65 * supply_parts[0] + 0.35 * supply_parts[1]
        consumer = (0.50 * positive_pct(frame[f"{prefix}_sales_amount"])
                    + 0.25 * positive_pct(frame[f"{prefix}_sales_share"])
                    + 0.25 * positive_pct(frame[f"{prefix}_time_share"]))
        frame[f"{prefix}_full_score"] = (0.70 * frame[f"{prefix}_supply_score"] + 0.30 * consumer).where(
            frame[f"{prefix}_sales_observed"] & frame[f"{prefix}_time_share"].notna()
            & frame[f"{prefix}_sales_share"].notna())

    both = frame.coffee_full_score.notna() & frame.bakery_full_score.notna()
    either_sale = frame.coffee_sales_observed | frame.bakery_sales_observed
    valid_supply = frame.total_stores_2025q4.gt(0) & frame.area_km2.gt(0)
    frame["full_score"] = (0.70 * frame.coffee_full_score + 0.30 * frame.bakery_full_score).where(both)
    frame["supply_only_score"] = (0.70 * frame.coffee_supply_score + 0.30 * frame.bakery_supply_score).where(valid_supply)
    frame["score_status"] = np.select([both, valid_supply & ~either_sale],
                                      ["complete", "supply_only"], default="insufficient")
    frame["score_status_reason"] = np.select([both, ~valid_supply, ~either_sale],
                                              ["both_cafe_industries_sales_observed", "no_valid_store_supply",
                                               "no_cafe_sales_rows"], default="partial_or_unusable_sales")
    frame["full_rank_within_complete"] = frame.loc[both, "full_score"].rank(ascending=False, method="min")
    only = frame.score_status.eq("supply_only")
    frame["supply_rank_within_supply_only"] = frame.loc[only, "supply_only_score"].rank(
        ascending=False, method="min")
    frame["study_v1_score"] = np.nan
    frame["study_v1_status"] = "incomplete_stay_evidence"
    frame["study_legacy_proxy_score"] = frame.study_stay_current_score
    frame["score_basis"] = "2025q4_official_stores_sales__2026_09_poi_diagnostic_only"
    frame.to_csv(OUT / "cafe_study_score_draft_786.csv", index=False, encoding="utf-8-sig")

    # Study proxies: compare identical 45% block with explicit alternatives.
    s3a, s3b = frame.study_cafe_percentile, frame.study_room_percentile
    other = (0.15 * frame.cafe_supply_percentile + 0.10 * frame.starbucks_percentile
             + 0.20 * frame.study_public_percentile + 0.10 * frame.access_percentile)
    compare = frame[["area_code", "area_name", "area_km2", "study_cafe_inside_count", "study_room_stores"]].copy()
    compare["s3a_percentile"] = s3a
    compare["s3b_percentile"] = s3b
    compare["legacy_both_30_15"] = other + 0.30 * s3a + 0.15 * s3b
    compare["primary_s3a_45"] = other + 0.45 * s3a
    compare["max_s3a_s3b_45"] = other + 0.45 * np.maximum(s3a, s3b)
    compare["interpretation"] = "proxy_sensitivity_not_verified_study_v1"
    compare.to_csv(OUT / "s3a_s3b_proxy_comparison_786.csv", index=False, encoding="utf-8-sig")
    baseline = names_top(compare, "legacy_both_30_15")
    summary = [{"variant": c, "top10_overlap_vs_legacy": overlap(baseline, names_top(compare, c)),
                "rank_spearman_vs_legacy": safe_spearman(compare.legacy_both_30_15, compare[c]),
                "s3a_s3b_input_spearman": safe_spearman(s3a, s3b),
                "top10_area_codes": "|".join(names_top(compare, c))}
               for c in ["legacy_both_30_15", "primary_s3a_45", "max_s3a_s3b_45"]]
    pd.DataFrame(summary).to_csv(OUT / "s3a_s3b_proxy_summary.csv", index=False, encoding="utf-8-sig")

    # Existing Euclidean public facilities only: does not claim a walk-network sensitivity.
    adj = frame[["area_code", "area_name", "study_public_inside_count", "study_public_nearby_only_count"]].copy()
    for weight, col in [(0.0, "inside_only"), (0.25, "inside_plus_25pct"), (0.5, "inside_plus_50pct")]:
        adj[col] = positive_pct(adj.study_public_inside_count + weight * adj.study_public_nearby_only_count)
    adj["distance_method"] = "euclidean_legacy"
    adj.to_csv(OUT / "adjacency_weight_euclidean_legacy_786.csv", index=False, encoding="utf-8-sig")
    base = names_top(adj, "inside_plus_25pct")
    pd.DataFrame([{"variant": col, "top10_overlap_vs_25pct": overlap(base, names_top(adj, col)),
                   "rank_spearman_vs_25pct": safe_spearman(adj.inside_plus_25pct, adj[col]),
                   "component": "public_facility_only_euclidean_legacy",
                   "top10_area_codes": "|".join(names_top(adj, col))}
                  for col in ["inside_only", "inside_plus_25pct", "inside_plus_50pct"]]).to_csv(
        OUT / "adjacency_weight_euclidean_legacy_summary.csv", index=False, encoding="utf-8-sig")

    # The four size adjustments use the same cafe store count, with explicit comparison baselines.
    size = frame[["area_code", "area_name", "area_km2", "total_stores_2025q4", "cafe_stores"]].copy()
    size["absolute_count"] = size.cafe_stores
    size["density"] = size.cafe_stores / size.area_km2.clip(lower=0.02)
    city_cafe = stores.loc[stores.svc_induty_cd.isin([CODE_COFFEE, CODE_BAKERY]), "stor_co"].sum()
    city_all = stores.stor_co.sum()
    city_share = city_cafe / city_all
    size["industry_lq"] = (size.cafe_stores / size.total_stores_2025q4.replace(0, np.nan)) / city_share
    x = np.column_stack([np.log(size.area_km2.clip(lower=0.02)), np.log1p(size.total_stores_2025q4)])
    y = np.log1p(size.cafe_stores)
    fitted = LinearRegression().fit(x, y)
    size["expected_log_count"] = fitted.predict(x)
    size["residual_log_count"] = y - size.expected_log_count
    size["residual_model_scope"] = "786_accessible_areas_2025q4"
    # A one-shop / three-shop LQ can dominate a rank despite negligible choice.
    size["ranking_evidence_eligible"] = size.cafe_stores.ge(10) & size.total_stores_2025q4.ge(50)
    size.to_csv(OUT / "cafe_size_correction_786.csv", index=False, encoding="utf-8-sig")
    ranked = size.loc[size.ranking_evidence_eligible].copy()
    original = names_top(ranked, "absolute_count")
    pd.DataFrame([{"method": col, "area_spearman": safe_spearman(size[col], size.area_km2),
                   "total_store_spearman": safe_spearman(size[col], size.total_stores_2025q4),
                   "top10_overlap_vs_absolute": overlap(original, names_top(ranked, col)),
                   "top10_area_codes": "|".join(names_top(ranked, col)),
                   "ranking_evidence_eligible_count": len(ranked),
                   "ranking_support_rule": "cafe_stores>=10_and_total_stores>=50; exploratory",
                   "city_reference_cafe_share": city_share,
                   "residual_model_r2": fitted.score(x, y)}
                  for col in ["absolute_count", "density", "industry_lq", "residual_log_count"]]).to_csv(
        OUT / "cafe_size_correction_summary.csv", index=False, encoding="utf-8-sig")

    # Apply the same four methods to the *official study-room industry* only.
    # These aggregated shops may overlap Kakao study-cafe POIs; no unique-place claim.
    room = frame[["area_code", "area_name", "area_km2", "total_stores_2025q4", "study_room_stores"]].copy()
    room["absolute_count"] = room.study_room_stores
    room["density"] = room.study_room_stores / room.area_km2.clip(lower=.02)
    city_room_share = stores.loc[stores.svc_induty_cd.eq(CODE_STUDY_ROOM), "stor_co"].sum() / city_all
    room["industry_lq"] = (room.study_room_stores / room.total_stores_2025q4.replace(0, np.nan)) / city_room_share
    room_y = np.log1p(room.study_room_stores)
    room_fit = LinearRegression().fit(x, room_y)
    room["expected_log_count"] = room_fit.predict(x)
    room["residual_log_count"] = room_y - room.expected_log_count
    room["ranking_evidence_eligible"] = room.study_room_stores.ge(3) & room.total_stores_2025q4.ge(50)
    room["proxy_warning"] = "official_study_room_industry_not_unique_verified_study_poi"
    room.to_csv(OUT / "study_room_size_correction_786.csv", index=False, encoding="utf-8-sig")
    room_ranked = room.loc[room.ranking_evidence_eligible]
    room_base = names_top(room_ranked, "absolute_count")
    pd.DataFrame([{"method": col, "area_spearman": safe_spearman(room[col], room.area_km2),
                   "total_store_spearman": safe_spearman(room[col], room.total_stores_2025q4),
                   "top10_overlap_vs_absolute": overlap(room_base, names_top(room_ranked, col)),
                   "top10_area_codes": "|".join(names_top(room_ranked, col)),
                   "ranking_evidence_eligible_count": len(room_ranked),
                   "ranking_support_rule": "study_room_stores>=3_and_total_stores>=50; exploratory",
                   "city_reference_study_room_share": city_room_share,
                   "residual_model_r2": room_fit.score(x, room_y)}
                  for col in ["absolute_count", "density", "industry_lq", "residual_log_count"]]).to_csv(
        OUT / "study_room_size_correction_summary.csv", index=False, encoding="utf-8-sig")

    # Evidence review: unknown is never silently changed to false or verified.
    review = kakao.loc[kakao.place_type.eq("starbucks"), ["place_id", "place_name"]].copy()
    review["source_dataset"] = "kakao_keyword_starbucks_20260918"
    extra = pois.loc[pois.facility_type.eq("large_cafe"), ["place_id", "facility_name", "source_url"]].rename(
        columns={"facility_name": "place_name", "source_url": "candidate_source_url"})
    extra["source_dataset"] = "osm_large_cafe_20260921"
    review = pd.concat([review, extra], ignore_index=True)
    review = review.drop_duplicates(["source_dataset", "place_id"])
    review["evidence_source_url"] = ""
    review["evidence_quote"] = ""
    for col in ["seat_verified", "study_allowed_verified", "mandatory_purchase"]:
        review[col] = "unknown"
    review["reviewer"] = ""
    review["reviewed_at"] = ""
    review["decision"] = "unknown"
    review["candidate_source_url"] = review.get("candidate_source_url", pd.Series(index=review.index)).fillna("")
    review = review[["place_id", "place_name", "evidence_source_url", "evidence_quote", "seat_verified",
                     "study_allowed_verified", "mandatory_purchase", "reviewer", "reviewed_at", "decision",
                     "source_dataset", "candidate_source_url"]]
    review.to_csv(OUT / "c_stay_s4_evidence_review.csv", index=False, encoding="utf-8-sig")

    # Do not put synthetic distances in a user-facing results table.
    pd.DataFrame(columns=["area_code", "place_id", "walk_distance_m", "walk_access_400", "walk_access_500",
                          "walk_access_600", "snap_gap_m", "network_source", "network_snapshot_date", "route_status",
                          "euclidean_legacy_distance_m"]).to_csv(OUT / "walk_network_access_pending.csv", index=False)
    pd.DataFrame(columns=["radius_m", "eligible_area_count", "top10_overlap_vs_400", "rank_spearman_vs_400",
                          "network_source", "status"]).to_csv(OUT / "walk_radius_sensitivity_pending.csv", index=False)

    assert len(frame) == frame.area_code.nunique() == 786
    assert frame.loc[frame.score_status.ne("complete"), "full_score"].isna().all()
    assert frame.study_v1_score.isna().all()
    assert len(review) == 427 and review.decision.eq("unknown").all()
    print("Wrote cafe/study draft and diagnostic tables to", OUT)
    print("Cafe score statuses:", frame.score_status.value_counts().to_dict())


if __name__ == "__main__":
    build()
