"""Appendix: discovery tags adapted from Yang et al. (2026), outside the 10/6 baseline.

Yang et al., "The characteristic analysis and pattern classification of
Beijing's commercial districts based on multi-source geographical big data",
Urban Informatics 5, 26 (2026). doi:10.1007/s44212-026-00116-z

The paper classifies districts by scale, functional mix, vitality rhythm and
reach. Without phone signals or origin-destination data, this script ports
the parts public Seoul data can support and keeps them as *tags*, never as
score inputs:

    scale_tier         POI-rank + vitality-rank sum, top 10% / 10-25% (paper's rule)
    purpose_driven     card transactions far above what the industry mix predicts
    low_transactions   far below it: cash/B2B trade or big-ticket goods, a caution, not a gem
    evening/weekend/young rhythm   share >= +2 SD within the same area type
    specialty_mix      industry entropy < mean - 2 SD (paper's comparison-goods rule)
    footfall_quadrant  optional, needs the Seoul OpenAPI street-population file

Every tag except scale_tier and specialty_mix must hold in >= 3 of the four
2025 quarters, including Q4. Tourism zones get no tags (their polygons
contain other candidate areas).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_food_shopping_v1 import read_zip_csv, spearman  # noqa: E402

QUARTERS = [20251, 20252, 20253, 20254]
BASE_QUARTER = 20254
TOURISM_TYPE = "관광특구"
MIN_COVERAGE = 0.6
MIN_DISCLOSED_STORES = 20
MIN_DISCLOSED_CELLS = 3
PURPOSE_DRIVEN_RATIO = 1.8
LOW_CAPTURE_RATIO = 1 / PURPOSE_DRIVEN_RATIO
RHYTHM_Z = 2.0
MIN_QUARTERS = 3
SPECIALTY_SD = 2.0
SCALE_TIERS = [(0.10, "도시핵심"), (0.25, "지역핵심")]
FOOTFALL_Z = 0.5
RHYTHMS = {
    "evening": ["시간대_17~21_매출_금액", "시간대_21~24_매출_금액"],
    "weekend": ["주말_매출_금액"],
    "young": ["연령대_10_매출_금액", "연령대_20_매출_금액"],
}
RHYTHM_LABEL = {"evening": "저녁형", "weekend": "주말형", "young": "10·20대형"}


def zscore_within(values: pd.Series, groups: pd.Series) -> pd.Series:
    return values.groupby(groups).transform(lambda s: (s - s.mean()) / s.std())


def expected_activity(stores: pd.DataFrame, sales: pd.DataFrame, keep: pd.Index) -> pd.DataFrame:
    """Observed vs expected card transactions for one quarter.

    Expected = stores x the Seoul median transactions per store of the same
    industry in the same area type, summed over disclosed cells. `ratio` is
    normalised so the median candidate area is 1.
    """
    m = stores.merge(sales, on=["area_code", "industry"])
    m["per_store"] = m.transactions / m.stores
    bench = m.groupby(["industry", "area_type"]).per_store.median().rename("bench")
    m = m.join(bench, on=["industry", "area_type"])
    m["expected"] = m.bench * m.stores
    g = m[m.area_code.isin(keep)].groupby("area_code").agg(
        observed=("transactions", "sum"), expected=("expected", "sum"),
        disclosed_stores=("stores", "sum"), cells=("stores", "size"),
    )
    total = stores[stores.area_code.isin(keep)].groupby("area_code").stores.sum()
    g["coverage"] = g.disclosed_stores / total.reindex(g.index)
    g = g[(g.disclosed_stores >= MIN_DISCLOSED_STORES) & (g.cells >= MIN_DISCLOSED_CELLS)]
    raw = g.observed / g.expected
    g["ratio"] = raw / raw.median()
    return g


def shannon_entropy(counts: pd.DataFrame) -> pd.Series:
    share = counts.div(counts.sum(axis=1), axis=0)
    return -(share * np.log(share.where(share > 0, 1))).sum(axis=1)


def scale_tier(store_rank_pct: pd.Series, activity_rank_pct: pd.Series) -> pd.Series:
    """Paper rule: rank sum of supply and vitality; top 10% city core, 10-25% district core."""
    combined = (store_rank_pct + activity_rank_pct).rank(pct=True, ascending=False)
    tier = pd.Series("생활권", index=combined.index)
    for cut, label in reversed(SCALE_TIERS):
        tier[combined <= cut] = label
    tier[combined.isna()] = "자료부족"
    return tier


def stable_flag(panel: pd.DataFrame, condition) -> pd.Series:
    """True when the condition holds in Q4 and in >= MIN_QUARTERS quarters."""
    hits = condition(panel).fillna(False)
    return hits.sum(axis=1).ge(MIN_QUARTERS) & hits[BASE_QUARTER]


def footfall_quadrant(foot: pd.Series, stores: pd.Series, transactions: pd.Series, area_type: pd.Series) -> pd.Series:
    traffic = zscore_within(np.log(foot / stores), area_type)
    conversion = zscore_within(np.log(transactions / foot), area_type)
    out = pd.Series("보통", index=foot.index)
    out[(traffic <= -FOOTFALL_Z) & (conversion >= FOOTFALL_Z)] = "목적형(사람 적고 결제 많음)"
    out[(traffic >= FOOTFALL_Z) & (conversion <= -FOOTFALL_Z)] = "통과형(사람 많고 결제 적음)"
    out[(traffic >= FOOTFALL_Z) & (conversion >= FOOTFALL_Z)] = "번화형"
    out[(traffic <= -FOOTFALL_Z) & (conversion <= -FOOTFALL_Z)] = "한산형"
    out[traffic.isna() | conversion.isna()] = ""
    return out


def build(candidates: pd.DataFrame, store_raw: pd.DataFrame, sales_raw: pd.DataFrame, scorecard: pd.DataFrame | None,
          footfall: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]:
    cand = candidates.set_index("area_code")
    keep = cand.index[cand.area_type_name != TOURISM_TYPE]
    stores = store_raw[store_raw.stor_co > 0].rename(columns={
        "trdar_cd": "area_code", "trdar_se_cd_nm": "area_type", "svc_induty_cd_nm": "industry", "stor_co": "stores",
        "stdr_yyqu_cd": "quarter"})
    sales = sales_raw.rename(columns={
        "상권_코드": "area_code", "서비스_업종_코드_명": "industry", "당월_매출_건수": "transactions",
        "당월_매출_금액": "amount", "기준_년분기_코드": "quarter"})
    for frame in (stores, sales):
        frame["area_code"] = frame.area_code.astype(str).str.zfill(7)

    ratio, coverage, rhythm = {}, {}, {r: {} for r in RHYTHMS}
    for q in QUARTERS:
        s_q, a_q = stores[stores.quarter == q], sales[sales.quarter == q]
        act = expected_activity(s_q[["area_code", "area_type", "industry", "stores"]], a_q[["area_code", "industry", "transactions"]], keep)
        ratio[q], coverage[q] = act.ratio, act.coverage
        by_area = a_q[a_q.area_code.isin(keep)].groupby("area_code")
        amount = by_area.amount.sum()
        for r, cols in RHYTHMS.items():
            share = sum(by_area[c].sum() for c in cols) / amount
            rhythm[r][q] = zscore_within(share, cand.area_type_name.reindex(share.index))
            if q == BASE_QUARTER:
                rhythm[r]["share"] = share

    out = cand[["area_name", "area_type_name", "primary_district_name"]].copy()
    ratio_p = pd.DataFrame(ratio).reindex(out.index)
    cov_p = pd.DataFrame(coverage).reindex(out.index)
    well_covered = cov_p.ge(MIN_COVERAGE)
    out["activity_ratio_q4"] = ratio_p[BASE_QUARTER]
    out["activity_coverage_q4"] = cov_p[BASE_QUARTER]
    out["activity_quarters_covered"] = well_covered.sum(axis=1)
    out["purpose_driven"] = stable_flag(ratio_p, lambda p: p.ge(PURPOSE_DRIVEN_RATIO) & well_covered)
    out["low_transactions"] = stable_flag(ratio_p, lambda p: p.le(LOW_CAPTURE_RATIO) & well_covered)
    for r in RHYTHMS:
        z = pd.DataFrame({q: rhythm[r][q] for q in QUARTERS}).reindex(out.index)
        out[f"{r}_share_q4"] = rhythm[r]["share"].reindex(out.index)
        out[f"{r}_z_q4"] = z[BASE_QUARTER]
        out[f"{r}_tag"] = stable_flag(z, lambda p: p.ge(RHYTHM_Z))

    base = stores[(stores.quarter == BASE_QUARTER) & stores.area_code.isin(keep)]
    mix = base.pivot_table(index="area_code", columns="industry", values="stores", aggfunc="sum", fill_value=0)
    entropy = shannon_entropy(mix)
    out["industry_entropy"] = entropy.reindex(out.index)
    out["dominant_industry"] = mix.idxmax(axis=1).reindex(out.index)
    out["dominant_share"] = (mix.max(axis=1) / mix.sum(axis=1)).reindex(out.index)
    out["specialty_mix"] = out.industry_entropy < entropy.mean() - SPECIALTY_SD * entropy.std()

    total_stores = mix.sum(axis=1).reindex(out.index)
    tx_q4 = sales[(sales.quarter == BASE_QUARTER)].groupby("area_code").transactions.sum().reindex(out.index)
    out["official_store_count_q4"] = total_stores
    out["card_transactions_q4"] = tx_q4
    out["scale_tier"] = scale_tier(total_stores.rank(pct=True), tx_q4.rank(pct=True))

    if footfall is not None:
        f = footfall[footfall.quarter == BASE_QUARTER].set_index("area_code").foot.reindex(out.index)
        # Only the derived quadrant is published; raw OpenAPI values stay outside the repo.
        out["footfall_quadrant"] = footfall_quadrant(f, total_stores, tx_q4, out.area_type_name)
        out.loc[out.activity_coverage_q4.lt(MIN_COVERAGE) | out.activity_coverage_q4.isna(), "footfall_quadrant"] = ""

    tourism = out.area_type_name == TOURISM_TYPE
    tag_cols = ["purpose_driven", "low_transactions", "specialty_mix"] + [f"{r}_tag" for r in RHYTHMS]
    out[tag_cols] = out[tag_cols].fillna(False).astype(bool)
    out.loc[tourism, tag_cols] = False
    out.loc[tourism, "scale_tier"] = ""
    out["discovery_tags"] = out.apply(lambda r: "|".join(_labels(r)), axis=1)

    summary = {
        "rows": int(len(out)), "tagged_universe": int(len(keep)),
        "purpose_driven": int(out.purpose_driven.sum()), "low_transactions": int(out.low_transactions.sum()),
        **{f"{r}_tag": int(out[f"{r}_tag"].sum()) for r in RHYTHMS},
        "specialty_mix": int(out.specialty_mix.sum()),
        "scale_tier": out.scale_tier.value_counts().to_dict(),
        "activity_ratio_q1_q4_spearman": round(float(spearman(ratio_p[20251], ratio_p[20254])), 3),
    }
    if footfall is not None:
        summary["footfall_quadrant"] = out.footfall_quadrant.value_counts().to_dict()
        pd_codes = out.index[out.purpose_driven]
        per_person = out.card_transactions_q4 / f
        summary["transactions_per_street_person_median"] = {
            "purpose_driven": round(float(per_person[pd_codes].median()), 3),
            "others_covered": round(float(per_person[out.activity_coverage_q4.ge(MIN_COVERAGE) & ~out.purpose_driven].median()), 3),
        }
    if scorecard is not None:
        sc = scorecard.set_index("area_code")
        for p in ["food", "shopping"]:
            out[f"v1_{p}_rank"] = sc[f"{p}_score"].rank(ascending=False, method="min").reindex(out.index)
        best = out[["v1_food_rank", "v1_shopping_rank"]].min(axis=1)
        out["outside_v1_top50"] = best > 50
        summary["purpose_driven_outside_v1_top50"] = int((out.purpose_driven & out.outside_v1_top50).sum())
        summary["young_tag_outside_v1_top50"] = int((out.young_tag & out.outside_v1_top50).sum())
    return out.reset_index(), summary


def tier_tops(tags: pd.DataFrame, scorecard: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Paper's answer to the size debate: compare purpose fit inside each scale tier."""
    sc = scorecard.set_index("area_code")
    frame = tags.set_index("area_code")[["area_name", "scale_tier", "discovery_tags"]].join(sc[[
        "food_score", "shopping_score", "food_score_basis", "shopping_score_basis", "food_eligible", "shopping_eligible"]])
    rows = []
    for tier in ["도시핵심", "지역핵심", "생활권"]:
        for p, label in [("food", "식사"), ("shopping", "쇼핑")]:
            pool = frame[(frame.scale_tier == tier) & frame[f"{p}_eligible"] & (frame[f"{p}_score_basis"] == "full")]
            top = pool.sort_values([f"{p}_score", "area_name"], ascending=[False, True]).head(n)
            for rank, (code, r) in enumerate(top.iterrows(), 1):
                rows.append({"scale_tier": tier, "purpose": label, "rank_in_tier": rank, "area_code": code,
                             "area_name": r.area_name, "score": round(r[f"{p}_score"], 2), "tier_pool": len(pool),
                             "discovery_tags": r.discovery_tags})
    return pd.DataFrame(rows)


def _labels(row: pd.Series) -> list[str]:
    labels = []
    if row.scale_tier in ("도시핵심", "지역핵심"):
        labels.append(row.scale_tier)
    if row.purpose_driven:
        labels.append("목적형 결제")
    if row.low_transactions:
        labels.append("결제 건수 적음(주의)")
    labels += [RHYTHM_LABEL[r] for r in RHYTHMS if row[f"{r}_tag"]]
    if row.specialty_mix:
        labels.append("전문시장형")
    return labels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv"))
    parser.add_argument("--area-sales", type=Path, default=Path("data/raw/commercial_area/commercial_sales_2025.zip"))
    parser.add_argument("--area-stores", type=Path, default=Path("data/raw/commercial_area/commercial_store_2025.zip"))
    parser.add_argument("--scorecard", type=Path, default=Path("data/processed/food_shopping_v1/official_area_food_shopping_v1_786.csv"))
    parser.add_argument("--street-population", type=Path, help="서울 열린데이터 VwsmTrdarFlpopQq CSV (저장소 밖, 선택)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/appendix_discovery_tags"))
    args = parser.parse_args()

    candidates = pd.read_csv(args.candidates, dtype={"area_code": str})
    candidates["area_code"] = candidates.area_code.str.zfill(7)
    scorecard = pd.read_csv(args.scorecard, dtype={"area_code": str}) if args.scorecard.exists() else None
    footfall = None
    if args.street_population:
        raw = pd.read_csv(args.street_population, dtype={"TRDAR_CD": str})
        footfall = pd.DataFrame({"area_code": raw.TRDAR_CD.str.zfill(7), "quarter": raw.STDR_YYQU_CD.astype(int), "foot": raw.TOT_FLPOP_CO})
    out, summary = build(candidates, read_zip_csv(args.area_stores), read_zip_csv(args.area_sales), scorecard, footfall)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_dir / "official_area_discovery_tags_786.csv", index=False, encoding="utf-8-sig")
    if scorecard is not None:
        tier_tops(out, scorecard).to_csv(args.output_dir / "scale_tier_top5_food_shopping.csv", index=False, encoding="utf-8-sig")
    (args.output_dir / "discovery_tags_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
