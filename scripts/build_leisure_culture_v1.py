#!/usr/bin/env python3
"""Build an auditable current leisure-culture score for 786 official areas.

The score keeps two time layers separate:

* 2025 commercial-area sales and store features form the historical context.
* 2026 POI observations are current explanatory signals only.  They are not
  used to claim historical prediction performance.

`호프-간이주점` is moved out of the food interpretation and added as a
night-leisure signal. Current Kakao POIs supplement the official 2025 source;
adult-nightlife POIs remain an explicit non-scoring tag.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

try:  # Supports both `python -m scripts...` and direct execution.
    from scripts.build_commercial_area_accessibility import normalize_area_code, read_zip_csv
except ModuleNotFoundError:
    from build_commercial_area_accessibility import normalize_area_code, read_zip_csv


NIGHTLIFE_INDUSTRIES = {"호프-간이주점"}
NIGHTLIFE_PRIME_TIME_COLUMNS = ["시간대_17~21_매출_금액", "시간대_21~24_매출_금액"]
REQUIRED_BASE = {
    "area_code", "area_name", "area_type_name", "purpose", "path_v0_score",
    "purpose_store_count", "purpose_sales_amount", "purpose_time_fit_amount",
    "minimum_period_ratio",
}
REQUIRED_POI = {
    "area_code", "feature_snapshot_date", "historical_2025_use_allowed",
    "culture_inside_count", "culture_buffer400_count", "culture_inside_diversity",
    "culture_buffer400_diversity",
}
REQUIRED_NIGHTLIFE = {
    "area_code", "nightlife_store_count", "nightlife_sales_amount",
    "nightlife_evening_sales_amount", "nightlife_late_sales_amount",
}
REQUIRED_AREA = {"area_code", "area_km2", "store_count_total"}


def _validate_unique(frame: pd.DataFrame, name: str) -> None:
    if "area_code" not in frame.columns:
        raise ValueError(f"{name}: missing area_code")
    if frame["area_code"].astype(str).duplicated().any():
        raise ValueError(f"duplicate area_code in {name}")


def _percentile(values: pd.Series) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if len(values) == 0:
        return values
    if values.nunique(dropna=False) <= 1:
        return pd.Series(50.0, index=values.index)
    return values.rank(method="average", pct=True) * 100.0


def _require(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing required columns: {', '.join(missing)}")


def _safe_corr(left: pd.Series, right: pd.Series) -> float | None:
    left = pd.to_numeric(left, errors="coerce")
    right = pd.to_numeric(right, errors="coerce")
    valid = left.notna() & right.notna()
    if valid.sum() < 2 or left[valid].nunique() < 2 or right[valid].nunique() < 2:
        return None
    return float(left[valid].corr(right[valid]))


def _recommendation_reason(row: pd.Series) -> str:
    """Create a concise, feature-grounded explanation for a candidate."""
    reasons: list[str] = []
    if row["culture_inside_count"] > 0:
        reasons.append(f"상권 내부 문화 POI {int(row['culture_inside_count'])}개")
    elif row["poi_nearby_only_count"] > 0:
        reasons.append(f"400m 내 문화 POI {int(row['poi_nearby_only_count'])}개")
    if row["night_food_walk400_count"] > 0:
        reasons.append(f"도보 400m 내 요리주점 {int(row['night_food_walk400_count'])}개")
    if row["nightlife_store_count"] > 0 and row["nightlife_prime_time_share"] > 0:
        reasons.append("저녁·심야 여가 소비 신호")
    if not reasons:
        reasons.append("2025년 여가 업종·매출 맥락")
    return " · ".join(reasons[:2])


def build_nightlife_features(stores: pd.DataFrame, sales: pd.DataFrame, quarter: int) -> pd.DataFrame:
    """Aggregate the official 2025 ``호프-간이주점`` signal by official area."""
    store = stores.copy()
    store["area_code"] = store["trdar_cd"].map(normalize_area_code)
    store = store[(store["stdr_yyqu_cd"].astype(int) == quarter) & store["svc_induty_cd_nm"].isin(NIGHTLIFE_INDUSTRIES)]
    store_agg = store.groupby("area_code", as_index=False).agg(nightlife_store_count=("stor_co", "sum"))

    sale = sales.copy()
    sale["area_code"] = sale["상권_코드"].map(normalize_area_code)
    sale = sale[(sale["기준_년분기_코드"].astype(int) == quarter) & sale["서비스_업종_코드_명"].isin(NIGHTLIFE_INDUSTRIES)].copy()
    for column in NIGHTLIFE_PRIME_TIME_COLUMNS + ["당월_매출_금액"]:
        if column not in sale.columns:
            sale[column] = 0.0
    sale_agg = sale.groupby("area_code", as_index=False).agg(
        nightlife_sales_amount=("당월_매출_금액", "sum"),
        nightlife_evening_sales_amount=("시간대_17~21_매출_금액", "sum"),
        nightlife_late_sales_amount=("시간대_21~24_매출_금액", "sum"),
    )
    return store_agg.merge(sale_agg, on="area_code", how="outer").fillna(0.0)


def area_measurements_from_geojson(path: Path, candidates: pd.DataFrame) -> pd.DataFrame:
    """Return projected polygon area and total stores for each candidate area."""
    data = json.loads(path.read_text(encoding="utf-8"))
    to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True).transform
    rows = []
    for feature in data["features"]:
        props = feature["properties"]
        polygon = transform(to_5179, shape(feature["geometry"]))
        rows.append({"area_code": normalize_area_code(props["area_code"]), "area_km2": polygon.area / 1_000_000})
    area = pd.DataFrame(rows)
    total = candidates[["area_code", "store_count_total"]].copy()
    total["area_code"] = total["area_code"].map(normalize_area_code)
    return area.merge(total, on="area_code", how="left")


def build_leisure_v1(
    base: pd.DataFrame,
    poi: pd.DataFrame,
    nightlife: pd.DataFrame,
    area: pd.DataFrame,
    current_nightlife_poi: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Combine 2025 context and current POI evidence without hiding time mismatch."""
    _require(base, REQUIRED_BASE, "base")
    _require(poi, REQUIRED_POI, "poi")
    _require(nightlife, REQUIRED_NIGHTLIFE, "nightlife")
    _require(area, REQUIRED_AREA, "area")
    for frame, name in [(poi, "poi"), (nightlife, "nightlife"), (area, "area")]:
        _validate_unique(frame, name)

    base = base[base["purpose"].eq("여가문화")].copy()
    if base.empty:
        raise ValueError("base: 여가문화 rows are required")
    _validate_unique(base, "base")
    for frame in [base, poi, nightlife, area]:
        frame["area_code"] = frame["area_code"].astype(str)

    # POI extracts repeat area metadata.  The historic ranking owns the
    # recommendation identity/type fields, preventing suffix ambiguity.
    poi_features = poi.drop(
        columns=[column for column in ["area_name", "area_type_name", "purpose", "minimum_period_ratio"] if column in poi.columns]
    )
    out = base.merge(poi_features, on="area_code", how="left", validate="one_to_one")
    out = out.merge(nightlife, on="area_code", how="left", validate="one_to_one")
    out = out.merge(area, on="area_code", how="left", validate="one_to_one")
    if current_nightlife_poi is None:
        current_nightlife_poi = pd.DataFrame({
            "area_code": out["area_code"].astype(str),
            "night_food_walk400_count": 0,
            "adult_nightlife_walk400_count": 0,
        })
    _require(current_nightlife_poi, {"area_code", "night_food_walk400_count", "adult_nightlife_walk400_count"}, "current_nightlife_poi")
    _validate_unique(current_nightlife_poi, "current_nightlife_poi")
    current_nightlife_poi = current_nightlife_poi.copy()
    current_nightlife_poi["area_code"] = current_nightlife_poi["area_code"].astype(str)
    current_nightlife_poi = current_nightlife_poi.drop(columns=["area_name"], errors="ignore")
    out = out.merge(current_nightlife_poi, on="area_code", how="left", validate="one_to_one")
    numeric = [
        "culture_inside_count", "culture_buffer400_count", "culture_inside_diversity",
        "culture_buffer400_diversity", "nightlife_store_count", "nightlife_sales_amount",
        "nightlife_evening_sales_amount", "nightlife_late_sales_amount", "area_km2", "store_count_total",
        "night_food_walk400_count", "adult_nightlife_walk400_count",
    ]
    out[numeric] = out[numeric].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    out["poi_nearby_only_count"] = (out["culture_buffer400_count"] - out["culture_inside_count"]).clip(lower=0)
    out["nightlife_prime_time_share"] = np.divide(
        out["nightlife_evening_sales_amount"] + out["nightlife_late_sales_amount"],
        out["nightlife_sales_amount"], out=np.zeros(len(out)), where=out["nightlife_sales_amount"] > 0,
    )
    out["nightlife_supply_score"] = _percentile(np.log1p(out["nightlife_store_count"]))
    out["nightlife_time_fit_score"] = _percentile(out["nightlife_prime_time_share"])
    out["nightlife_2025_score"] = 0.60 * out["nightlife_supply_score"] + 0.40 * out["nightlife_time_fit_score"]
    out["historical_leisure_context_score"] = 0.70 * out["path_v0_score"] + 0.30 * out["nightlife_2025_score"]

    safe_area = out["area_km2"].clip(lower=0.01)
    out["current_poi_density_per_km2"] = out["culture_inside_count"] / safe_area
    out["current_poi_density_score"] = _percentile(np.log1p(out["current_poi_density_per_km2"]))
    out["current_poi_diversity_score"] = _percentile(out["culture_inside_diversity"])
    out["current_night_food_density_per_km2"] = out["night_food_walk400_count"] / safe_area
    out["current_night_food_score"] = _percentile(np.log1p(out["current_night_food_density_per_km2"]))
    out["adult_nightlife_recommendation_eligible"] = False
    out["current_poi_explanation_score"] = (
        0.55 * out["current_poi_density_score"]
        + 0.25 * out["current_poi_diversity_score"]
        + 0.20 * out["current_night_food_score"]
    )
    out["current_poi_explanation_without_night_food"] = (
        0.6875 * out["current_poi_density_score"] + 0.3125 * out["current_poi_diversity_score"]
    )
    out["current_exploration_score_raw"] = 0.70 * out["historical_leisure_context_score"] + 0.30 * out["current_poi_explanation_score"]
    out["current_exploration_without_night_food"] = (
        0.70 * out["historical_leisure_context_score"] + 0.30 * out["current_poi_explanation_without_night_food"]
    )

    # Residualise the current score against area and total store scale.  This is
    # an audit/alternative ranking, not a claim that size has causal effect.
    design = np.column_stack([
        np.ones(len(out)), np.log1p(safe_area), np.log1p(out["store_count_total"].clip(lower=0)),
    ])
    fitted = design @ np.linalg.lstsq(design, out["current_exploration_score_raw"].to_numpy(), rcond=None)[0]
    out["size_adjustment_residual"] = out["current_exploration_score_raw"] - fitted
    out["leisure_size_adjusted_score"] = _percentile(out["size_adjustment_residual"])
    out["recommendation_eligible"] = ~out["area_type_name"].eq("관광특구")
    out["recommendation_exclusion_reason"] = np.where(
        out["recommendation_eligible"], "", "tourism_special_zone"
    )
    out["current_poi_historical_use_allowed"] = out["historical_2025_use_allowed"].fillna(False).astype(bool)
    out["recommendation_reason"] = out.apply(_recommendation_reason, axis=1)
    out["leisure_rank_eligible"] = out["leisure_size_adjusted_score"].where(out["recommendation_eligible"]).rank(method="min", ascending=False)
    out = out.sort_values(["recommendation_eligible", "leisure_rank_eligible", "area_code"], ascending=[False, True, True]).reset_index(drop=True)
    raw_area_corr = _safe_corr(out["current_exploration_score_raw"], out["area_km2"])
    raw_store_corr = _safe_corr(out["current_exploration_score_raw"], out["store_count_total"])
    adjusted_area_corr = _safe_corr(out["leisure_size_adjusted_score"], out["area_km2"])
    adjusted_store_corr = _safe_corr(out["leisure_size_adjusted_score"], out["store_count_total"])
    eligible_mask = out["recommendation_eligible"]
    top_with = set(out.loc[eligible_mask].nlargest(10, "current_exploration_score_raw")["area_code"])
    top_without = set(out.loc[eligible_mask].nlargest(10, "current_exploration_without_night_food")["area_code"])
    audit = {
        "area_count": int(len(out)),
        "unique_area_count": int(out["area_code"].nunique()),
        "tourism_special_zone_count": int((~out["recommendation_eligible"]).sum()),
        "eligible_area_count": int(out["recommendation_eligible"].sum()),
        "poi_snapshot_dates": sorted(out["feature_snapshot_date"].dropna().astype(str).unique().tolist()),
        "historical_2025_use_allowed_for_current_poi": bool(out["current_poi_historical_use_allowed"].all()),
        "nightlife_industries_in_source": sorted(NIGHTLIFE_INDUSTRIES),
        "official_2025_categories_not_separately_available": ["요리주점", "유흥주점"],
        "current_night_food_feature": "night_food_walk400_count",
        "adult_nightlife_used_in_score": False,
        "raw_top10_overlap_with_vs_without_current_night_food": len(top_with & top_without),
        "raw_score_vs_area_km2_pearson": raw_area_corr,
        "raw_score_vs_total_stores_pearson": raw_store_corr,
        "adjusted_score_vs_area_km2_pearson": adjusted_area_corr,
        "adjusted_score_vs_total_stores_pearson": adjusted_store_corr,
    }
    return out, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="data/processed/commercial_area_purpose_features/official_area_purpose_latest_rankings.csv")
    parser.add_argument("--poi", default="data/external/official_area_poi_features_20260916.csv")
    parser.add_argument("--stores", default="data/raw/commercial_area/commercial_store_2025.zip")
    parser.add_argument("--sales", default="data/raw/commercial_area/commercial_sales_2025.zip")
    parser.add_argument("--candidates", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv")
    parser.add_argument("--areas", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    parser.add_argument("--current-nightlife-poi", default="data/processed/nightlife_poi_v1/official_area_nightlife_poi_features_786.csv")
    parser.add_argument("--output-dir", default="data/processed/leisure_culture_v1")
    args = parser.parse_args()

    base = pd.read_csv(args.base, dtype={"area_code": str})
    base = base[(base["purpose"] == "여가문화") & (base["quarter"] == base["quarter"].max())].copy()
    candidates = pd.read_csv(args.candidates, dtype={"area_code": str})
    nightlife = build_nightlife_features(read_zip_csv(Path(args.stores)), read_zip_csv(Path(args.sales)), int(base["quarter"].max()))
    area = area_measurements_from_geojson(Path(args.areas), candidates)
    result, audit = build_leisure_v1(
        base, pd.read_csv(args.poi, dtype={"area_code": str}), nightlife, area,
        current_nightlife_poi=pd.read_csv(args.current_nightlife_poi, dtype={"area_code": str}),
    )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / "official_area_leisure_culture_v1_786.csv", index=False, encoding="utf-8-sig")
    eligible = result[result["recommendation_eligible"]].copy()
    eligible.nlargest(10, "current_exploration_score_raw").to_csv(
        output / "leisure_culture_v1_raw_top10.csv", index=False, encoding="utf-8-sig"
    )
    eligible.head(10).to_csv(output / "leisure_culture_v1_size_adjusted_top10.csv", index=False, encoding="utf-8-sig")
    (output / "leisure_culture_v1_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
