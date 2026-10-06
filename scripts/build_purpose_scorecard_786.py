"""Join the five purpose scores into one 786-area scorecard with combo Top 10s.

Each purpose is read from its owner's latest file listed in SOURCES. Only food
and shopping follow the 10/1 Purpose Score v2 rule today; cafe, study and
leisure are earlier drafts and carry `source_status=provisional` until their
owners publish v2 files, at which point only SOURCES needs to change.

Scores from different methods are not on one scale, so every purpose is
converted to a percentile among the 786 areas before combining. Combos are the
equal mean of member percentiles, listed only when every member is >= 50 and
the area is eligible for every member; overlapping areas are removed as in v1.
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_food_shopping_v1 import COMBO_MIN_PERCENTILE, percentile, pick_top  # noqa: E402

PURPOSE_LABELS = {"food": "식사", "cafe": "카페", "study": "공부", "shopping": "쇼핑", "leisure": "여가문화"}
FOOD_SHOPPING = "data/processed/food_shopping_v1/official_area_food_shopping_v1_786.csv"
SOURCES = {
    "food": {
        "path": FOOD_SHOPPING, "score": "food_score", "status": "food_score_basis", "eligible": "food_eligible",
        "version": "food_shopping_v1 (김건우, 2026-10-06, Purpose Score v2)", "source_status": "official_v2",
    },
    "shopping": {
        "path": FOOD_SHOPPING, "score": "shopping_score", "status": "shopping_score_basis", "eligible": "shopping_eligible",
        "version": "food_shopping_v1 (김건우, 2026-10-06, Purpose Score v2)", "source_status": "official_v2",
    },
    "cafe": {
        "path": "data/reference/food_shopping/cafe_size_adjusted_score_draft_20260929.csv",
        "score": "cafe_size_adjusted_supply_only_score", "status": "score_status", "eligible": "recommendation_eligible",
        "version": "cafe draft (장한별, 2026-09-29, 잔차 방식 공급점수)", "source_status": "provisional",
    },
    "study": {
        "path": "data/processed/week2_integration/official_area_week2_integration.csv",
        "score": "study_stay_current_score", "status": None, "eligible": None,
        "version": "study_stay_current (2주차 통합, 2026-09-22, PATH-v0 계열)", "source_status": "provisional",
    },
    "leisure": {
        "path": "data/reference/purpose_scorecard/leisure_culture_v1_20260930.csv",
        "score": "leisure_size_adjusted_score", "status": None, "eligible": "recommendation_eligible",
        "version": "leisure_culture_v1 (지우진, 2026-09-30, 잔차 방식)", "source_status": "provisional",
    },
}
# Areas whose food/shopping score has no sales signal are listed separately in
# v1; combos here keep them out so a combo never mixes the two bases.
FULL_BASIS = "full"


def load_purpose(purpose: str, root: Path) -> pd.DataFrame:
    src = SOURCES[purpose]
    frame = pd.read_csv(root / src["path"], dtype={"area_code": str})
    frame["area_code"] = frame.area_code.str.zfill(7)
    frame = frame.drop_duplicates("area_code").set_index("area_code")
    out = pd.DataFrame(index=frame.index)
    out[f"{purpose}_score"] = frame[src["score"]]
    out[f"{purpose}_status"] = frame[src["status"]] if src["status"] else ""
    out[f"{purpose}_eligible"] = frame[src["eligible"]].astype(bool) if src["eligible"] else True
    out[f"{purpose}_source_status"] = src["source_status"]
    return out


def build(base: pd.DataFrame, purposes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    card = base.set_index("area_code")
    for purpose, frame in purposes.items():
        card = card.join(frame, how="left")
        card[f"{purpose}_pct"] = percentile(card[f"{purpose}_score"])
        card[f"{purpose}_eligible"] = card[f"{purpose}_eligible"].fillna(False).astype(bool) & card.recommendation_eligible
        if purpose in ("food", "shopping"):
            card[f"{purpose}_combo_ready"] = card[f"{purpose}_eligible"] & (card[f"{purpose}_status"] == FULL_BASIS)
        else:
            card[f"{purpose}_combo_ready"] = card[f"{purpose}_eligible"] & card[f"{purpose}_score"].notna()
    pct = card[[f"{p}_pct" for p in purposes]]
    pct.columns = list(purposes)
    card["best_purpose"] = pct.idxmax(axis=1).map(PURPOSE_LABELS)
    card["best_purpose_pct"] = pct.max(axis=1)
    card["purpose_rank_order"] = pct.apply(lambda r: "|".join(PURPOSE_LABELS[p] for p in r.sort_values(ascending=False).index), axis=1)
    return card.reset_index()


def combo_tables(card: pd.DataFrame, geom: gpd.GeoSeries, purposes: list[str]) -> pd.DataFrame:
    frame = card.set_index("area_code")
    rows = []
    for size in (2, 3):
        for members in combinations(purposes, size):
            ready = np.logical_and.reduce([frame[f"{m}_combo_ready"] for m in members])
            floor = np.logical_and.reduce([frame[f"{m}_pct"] >= COMBO_MIN_PERCENTILE for m in members])
            pool = frame[ready & floor].copy()
            pool["combo_score"] = pool[[f"{m}_pct" for m in members]].mean(axis=1)
            pool["weakest_purpose_pct"] = pool[[f"{m}_pct" for m in members]].min(axis=1)
            top = pick_top(pool, "combo_score", geom)
            provisional = [PURPOSE_LABELS[m] for m in members if SOURCES[m]["source_status"] != "official_v2"]
            for code, r in top.iterrows():
                rows.append({
                    "combo_size": size,
                    "combo": "+".join(members),
                    "combo_label": "+".join(PURPOSE_LABELS[m] for m in members),
                    "rank": int(r["rank"]),
                    "area_code": code,
                    "area_name": r.area_name,
                    "area_type_name": r.area_type_name,
                    "combo_score": round(r.combo_score, 2),
                    "weakest_purpose_pct": round(r.weakest_purpose_pct, 2),
                    **{f"{m}_pct": round(r[f"{m}_pct"], 2) for m in members},
                    "small_area": bool(r.small_area),
                    "pool_size": len(pool),
                    "provisional_purposes": "|".join(provisional),
                })
    return pd.DataFrame(rows)


def qa(card: pd.DataFrame, combos: pd.DataFrame, purposes: list[str]) -> dict:
    score_cols = [f"{p}_score" for p in purposes]
    pct_cols = [f"{p}_pct" for p in purposes]
    spearman = card[pct_cols].rank().corr().round(3)
    spearman.index = spearman.columns = purposes
    return {
        "rows": int(len(card)),
        "area_code_unique": bool(card.area_code.is_unique),
        "score_missing": {c: int(card[c].isna().sum()) for c in score_cols},
        "pct_range": [round(float(card[pct_cols].min().min()), 3), round(float(card[pct_cols].max().max()), 3)],
        "combo_ready_counts": {p: int(card[f"{p}_combo_ready"].sum()) for p in purposes},
        "combo_lists": int(combos.groupby("combo").ngroups),
        "combo_rows_below_floor": int((combos[[c for c in combos if c.endswith("_pct") and c != "weakest_purpose_pct"]] < COMBO_MIN_PERCENTILE).any(axis=1).sum()),
        "combo_tourism_rows": int(card.set_index("area_code").loc[combos.area_code].is_tourism_zone.sum()),
        "purpose_percentile_spearman": spearman.to_dict(),
        "sources": {p: {k: SOURCES[p][k] for k in ("version", "source_status", "score")} for p in purposes},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--areas", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/purpose_scorecard_786"))
    args = parser.parse_args()

    fs = pd.read_csv(args.root / FOOD_SHOPPING, dtype={"area_code": str})
    base_cols = ["area_code", "area_name", "area_type_name", "minimum_period_ratio", "access_tier", "recommendation_eligible",
                 "is_tourism_zone", "inside_tourism_zone", "small_area", "wide_area", "wholesale_decision", "walk_distance_basis"]
    base = fs[base_cols].copy()
    purposes = list(PURPOSE_LABELS)
    card = build(base, {p: load_purpose(p, args.root) for p in purposes})
    subtypes = fs.set_index("area_code")[["food_best_subtype", "food_top_subtypes", "best_subtype_label", "top3_subtype_labels"]]
    card = card.join(subtypes.rename(columns={"best_subtype_label": "food_shopping_best_subtype", "top3_subtype_labels": "food_shopping_top3_subtypes"}), on="area_code")

    areas = gpd.read_file(args.areas).to_crs(5181)
    areas["area_code"] = areas.area_code.astype(str).str.zfill(7)
    combos = combo_tables(card, areas.set_index("area_code").geometry, purposes)
    report = qa(card, combos, purposes)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    card.to_csv(args.output_dir / "official_area_purpose_scorecard_786.csv", index=False, encoding="utf-8-sig")
    combos.to_csv(args.output_dir / "purpose_combo_top10.csv", index=False, encoding="utf-8-sig")
    (args.output_dir / "purpose_scorecard_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("rows", "area_code_unique", "score_missing", "combo_ready_counts", "combo_lists", "combo_rows_below_floor")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
