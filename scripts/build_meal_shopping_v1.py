#!/usr/bin/env python3
"""Build an auditable meal and shopping recommendation baseline for 786 areas."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

try:
    from scripts.build_commercial_area_accessibility import normalize_area_code, read_zip_csv
except ModuleNotFoundError:
    from build_commercial_area_accessibility import normalize_area_code, read_zip_csv


MEAL_TAXONOMY = {
    "한식음식점": "한식", "중식음식점": "중식", "일식음식점": "일식", "양식음식점": "양식",
    "분식전문점": "간편식", "패스트푸드점": "간편식", "치킨전문점": "치킨",
}
SHOPPING_TAXONOMY = {
    "일반의류": "패션·뷰티", "한복점": "패션·뷰티", "유아의류": "패션·뷰티", "신발": "패션·뷰티",
    "가방": "패션·뷰티", "화장품": "패션·뷰티", "미용재료": "패션·뷰티", "안경": "패션·뷰티",
    "시계및귀금속": "패션·뷰티", "의류임대": "패션·뷰티",
    "슈퍼마켓": "식품·생활", "편의점": "식품·생활", "미곡판매": "식품·생활", "육류판매": "식품·생활",
    "수산물판매": "식품·생활", "청과상": "식품·생활", "반찬가게": "식품·생활",
    "문구": "취미·문화", "서적": "취미·문화", "완구": "취미·문화", "악기": "취미·문화",
    "예술품": "취미·문화", "화초": "취미·문화", "운동/경기용품": "취미·문화",
    "가전제품": "디지털·홈", "핸드폰": "디지털·홈", "컴퓨터및주변장치판매": "디지털·홈",
    "가구": "디지털·홈", "중고가구": "디지털·홈", "인테리어": "디지털·홈", "조명용품": "디지털·홈",
    "철물점": "디지털·홈", "섬유제품": "디지털·홈",
    "의약품": "건강·반려", "의료기기": "건강·반려", "애완동물": "건강·반려",
}
WHOLESALE_NAME_PATTERN = re.compile(r"도매|청과물시장|농수산물시장|수산시장|축산물시장|건축자재시장|자동차부품상가|공구상가")


def map_meal_subcategory(industry: str) -> str | None:
    return MEAL_TAXONOMY.get(str(industry).strip())


def map_shopping_subcategory(industry: str) -> str | None:
    return SHOPPING_TAXONOMY.get(str(industry).strip())


def classify_market_channel(area_name: str, area_type_name: str) -> str:
    if str(area_type_name) != "전통시장":
        return "일반상권"
    return "도매·전문시장" if WHOLESALE_NAME_PATTERN.search(str(area_name)) else "일반소매"


def add_meal_price_bands(frame: pd.DataFrame) -> pd.DataFrame:
    """Classify lunch tickets relative to the same detailed menu category."""
    out = frame.copy()
    amount = pd.to_numeric(out["lunch_sales_amount"], errors="coerce")
    count = pd.to_numeric(out["lunch_sales_count"], errors="coerce")
    out["lunch_average_ticket"] = np.divide(amount, count, out=np.full(len(out), np.nan), where=count > 0)
    out["meal_price_band"] = "정보없음"
    valid = out["lunch_average_ticket"].notna()
    for _, indices in out[valid].groupby("industry").groups.items():
        values = out.loc[indices, "lunch_average_ticket"]
        low, high = values.quantile([0.25, 0.75])
        out.loc[indices, "meal_price_band"] = np.select(
            [values <= low, values >= high], ["저가", "고가"], default="중가"
        )
    return out


def _percentile(values: pd.Series) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if values.nunique() <= 1:
        return pd.Series(50.0, index=values.index)
    return values.rank(method="average", pct=True) * 100


def _safe_corr(left: pd.Series, right: pd.Series) -> float | None:
    left, right = pd.to_numeric(left, errors="coerce"), pd.to_numeric(right, errors="coerce")
    valid = left.notna() & right.notna()
    if valid.sum() < 2 or left[valid].nunique() < 2 or right[valid].nunique() < 2:
        return None
    return float(left[valid].corr(right[valid]))


def _area_measurements(areas: gpd.GeoDataFrame) -> pd.DataFrame:
    frame = areas[["area_code", "geometry"]].copy()
    frame["area_code"] = frame["area_code"].map(normalize_area_code)
    metric = frame.to_crs("EPSG:5186")
    return pd.DataFrame({"area_code": frame.area_code, "area_km2": metric.geometry.area / 1_000_000})


def _prepare_detail(stores: pd.DataFrame, sales: pd.DataFrame, area_codes: set[str], quarter: int) -> pd.DataFrame:
    store = stores.copy()
    store["quarter"] = store["stdr_yyqu_cd"].astype(int)
    store["area_code"] = store["trdar_cd"].map(normalize_area_code)
    store["industry"] = store["svc_induty_cd_nm"].astype(str)
    store = store[(store.quarter == quarter) & store.area_code.isin(area_codes)].copy()
    store["meal_subcategory"] = store.industry.map(map_meal_subcategory)
    store["shopping_subcategory"] = store.industry.map(map_shopping_subcategory)
    store["purpose"] = np.where(store.meal_subcategory.notna(), "식사", np.where(store.shopping_subcategory.notna(), "쇼핑", None))
    store["subcategory"] = store.meal_subcategory.fillna(store.shopping_subcategory)
    store = store[store.purpose.notna()].groupby(
        ["area_code", "purpose", "subcategory", "industry"], as_index=False
    ).agg(store_count=("stor_co", "sum"))

    sale = sales.copy()
    sale["quarter"] = sale["기준_년분기_코드"].astype(int)
    sale["area_code"] = sale["상권_코드"].map(normalize_area_code)
    sale["industry"] = sale["서비스_업종_코드_명"].astype(str)
    sale = sale[(sale.quarter == quarter) & sale.area_code.isin(area_codes)].copy()
    sale["meal_subcategory"] = sale.industry.map(map_meal_subcategory)
    sale["shopping_subcategory"] = sale.industry.map(map_shopping_subcategory)
    sale["purpose"] = np.where(sale.meal_subcategory.notna(), "식사", np.where(sale.shopping_subcategory.notna(), "쇼핑", None))
    sale["subcategory"] = sale.meal_subcategory.fillna(sale.shopping_subcategory)
    sale = sale[sale.purpose.notna()].copy()
    for column in [
        "당월_매출_금액", "당월_매출_건수", "시간대_11~14_매출_금액", "시간대_건수~14_매출_건수",
        "시간대_14~17_매출_금액", "시간대_17~21_매출_금액",
    ]:
        if column not in sale:
            sale[column] = 0.0
    sale["time_fit_sales_amount"] = np.where(
        sale.purpose.eq("식사"),
        sale["시간대_11~14_매출_금액"] + sale["시간대_17~21_매출_금액"],
        sale["시간대_14~17_매출_금액"] + sale["시간대_17~21_매출_금액"],
    )
    sale_agg = sale.groupby(["area_code", "purpose", "subcategory", "industry"], as_index=False).agg(
        sales_amount=("당월_매출_금액", "sum"), sales_count=("당월_매출_건수", "sum"),
        time_fit_sales_amount=("time_fit_sales_amount", "sum"),
        lunch_sales_amount=("시간대_11~14_매출_금액", "sum"),
        lunch_sales_count=("시간대_건수~14_매출_건수", "sum"),
    )
    sale_agg = add_meal_price_bands(sale_agg)
    detail = store.merge(sale_agg, on=["area_code", "purpose", "subcategory", "industry"], how="outer")
    detail["store_count"] = detail.store_count.fillna(0.0)
    detail["sales_observed"] = detail.sales_amount.notna()
    for column in ["sales_amount", "sales_count", "time_fit_sales_amount", "lunch_sales_amount", "lunch_sales_count"]:
        detail[column] = detail[column].fillna(0.0)
    detail["meal_price_band"] = detail.meal_price_band.fillna("정보없음")
    return detail.sort_values(["purpose", "area_code", "subcategory", "industry"]).reset_index(drop=True)


def _impute_aggregate_sales(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["sales_imputed"] = False
    out["sales_amount_for_score"] = out["sales_amount"]
    observed = out[out.sales_observed & (out.purpose == "쇼핑") & (out.purpose_store_count > 0)].copy()
    observed["sales_per_store"] = observed.sales_amount / observed.purpose_store_count
    medians = observed.groupby("area_type_name").sales_per_store.median()
    fallback = float(observed.sales_per_store.median()) if not observed.empty else 0.0
    mask = (out.purpose == "쇼핑") & (~out.sales_observed) & (out.purpose_store_count > 0)
    rates = out.loc[mask, "area_type_name"].map(medians).fillna(fallback)
    out.loc[mask, "sales_amount_for_score"] = out.loc[mask, "purpose_store_count"] * rates.to_numpy()
    out.loc[mask, "sales_imputed"] = True
    return out


def _recommendation_reason(row: pd.Series) -> str:
    parts = [f"주요 유형 {row['top_subcategory']}", f"관련 점포 {int(row['purpose_store_count'])}개"]
    if bool(row["sales_imputed"]):
        parts.append("총매출 비공개로 추정 매출 사용")
    elif row["sales_category_coverage"] < 1:
        parts.append(f"업종 매출 공개율 {row['sales_category_coverage']:.0%}")
    else:
        parts.append("점포·매출 모두 관측")
    return " · ".join(parts)


def build_combined_ranking(frame: pd.DataFrame) -> pd.DataFrame:
    """Return areas usable for a meal+shopping request with both signals observed."""
    eligible = frame[frame.recommendation_eligible & frame.recommendation_high_confidence].copy()
    scores = eligible.pivot(index=["area_code", "area_name"], columns="purpose", values="size_adjusted_score")
    scores = scores.dropna(subset=["식사", "쇼핑"]).reset_index()
    scores["combined_score"] = 0.50 * scores["식사"] + 0.50 * scores["쇼핑"]
    scores["combined_rank"] = scores.combined_score.rank(method="min", ascending=False)
    return scores.sort_values(["combined_rank", "area_code"]).reset_index(drop=True)


def build_meal_shopping_v1(
    stores: pd.DataFrame,
    sales: pd.DataFrame,
    candidates: pd.DataFrame,
    areas: gpd.GeoDataFrame,
    quarter: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    candidates = candidates.copy()
    candidates["area_code"] = candidates.area_code.map(normalize_area_code)
    candidates = candidates.drop_duplicates("area_code")
    candidates["market_channel"] = candidates.apply(
        lambda row: classify_market_channel(row.area_name, row.area_type_name), axis=1
    )
    candidates = candidates.merge(_area_measurements(areas), on="area_code", how="left", validate="one_to_one")
    detail = _prepare_detail(stores, sales, set(candidates.area_code), quarter)
    detail["store_industry_present"] = detail.store_count.gt(0).astype(int)
    detail["sales_industry_observed"] = detail.sales_observed.astype(int)
    agg = detail.groupby(["area_code", "purpose"], as_index=False).agg(
        purpose_store_count=("store_count", "sum"),
        subcategory_diversity=("subcategory", lambda x: int(x[detail.loc[x.index, "store_count"] > 0].nunique())),
        industry_diversity=("industry", lambda x: int(x[detail.loc[x.index, "store_count"] > 0].nunique())),
        sales_amount=("sales_amount", "sum"), sales_count=("sales_count", "sum"),
        time_fit_sales_amount=("time_fit_sales_amount", "sum"),
        sales_observed=("sales_observed", "max"),
        store_industry_count=("store_industry_present", "sum"),
        sales_industry_count=("sales_industry_observed", "sum"),
    )
    subcategory_wide = detail.pivot_table(
        index=["area_code", "purpose"], columns="subcategory", values="store_count", aggfunc="sum", fill_value=0
    )
    subcategory_wide.columns = [f"store_{column}" for column in subcategory_wide.columns]
    subcategory_wide = subcategory_wide.reset_index()
    top_subcategory = (
        detail.groupby(["area_code", "purpose", "subcategory"], as_index=False).store_count.sum()
        .sort_values(["area_code", "purpose", "store_count", "subcategory"], ascending=[True, True, False, True])
        .drop_duplicates(["area_code", "purpose"])
        .rename(columns={"subcategory": "top_subcategory"})[["area_code", "purpose", "top_subcategory"]]
    )
    grid = pd.MultiIndex.from_product([candidates.area_code, ["식사", "쇼핑"]], names=["area_code", "purpose"]).to_frame(index=False)
    out = grid.merge(candidates, on="area_code", how="left", validate="many_to_one").merge(
        agg, on=["area_code", "purpose"], how="left", validate="one_to_one"
    )
    out = out.merge(subcategory_wide, on=["area_code", "purpose"], how="left", validate="one_to_one")
    out = out.merge(top_subcategory, on=["area_code", "purpose"], how="left", validate="one_to_one")
    subcategory_columns = [
        column for column in out.columns
        if column.startswith("store_") and column not in {"store_count_total", "store_industry_count"}
    ]
    numeric = [
        "purpose_store_count", "subcategory_diversity", "industry_diversity", "sales_amount", "sales_count",
        "time_fit_sales_amount", "store_industry_count", "sales_industry_count",
    ] + subcategory_columns
    out[numeric] = out[numeric].fillna(0.0)
    out["top_subcategory"] = out.top_subcategory.fillna("해당없음")
    out["sales_observed"] = out.sales_observed.fillna(False).astype(bool)
    out["sales_category_coverage"] = np.divide(
        out.sales_industry_count, out.store_industry_count,
        out=np.zeros(len(out)), where=out.store_industry_count.to_numpy() > 0,
    ).clip(upper=1)
    out = _impute_aggregate_sales(out)
    safe_area = out.area_km2.clip(lower=0.01)
    out["store_density_per_km2"] = out.purpose_store_count / safe_area
    out["purpose_store_share"] = np.divide(
        out.purpose_store_count, out.store_count_total,
        out=np.zeros(len(out)), where=pd.to_numeric(out.store_count_total, errors="coerce").fillna(0).to_numpy() > 0,
    )
    for purpose, indices in out.groupby("purpose").groups.items():
        purpose_stores = out.loc[indices, "purpose_store_count"].sum()
        all_stores = out.loc[indices, "store_count_total"].sum()
        global_share = purpose_stores / all_stores if all_stores else 0
        out.loc[indices, "location_quotient"] = out.loc[indices, "purpose_store_share"] / global_share if global_share else 0
    out["sales_density_per_km2"] = out.sales_amount_for_score / safe_area
    out["transaction_density_per_km2"] = out.sales_count / safe_area
    out["time_fit_share"] = np.divide(
        out.time_fit_sales_amount, out.sales_amount,
        out=np.zeros(len(out)), where=out.sales_amount.to_numpy() > 0,
    )
    out["access_score"] = _percentile(out.minimum_period_ratio)
    for source, target, use_log in [
        ("store_density_per_km2", "store_density_score", True),
        ("purpose_store_share", "store_share_score", False),
        ("subcategory_diversity", "subcategory_diversity_score", False),
        ("location_quotient", "specialization_score", True),
        ("sales_density_per_km2", "sales_density_score", True),
        ("transaction_density_per_km2", "transaction_density_score", True),
        ("time_fit_share", "time_fit_score", False),
    ]:
        out[target] = out.groupby("purpose")[source].transform(lambda values: _percentile(np.log1p(values) if use_log else values))
    out["supply_score"] = (
        0.35 * out.store_density_score + 0.25 * out.store_share_score
        + 0.20 * out.subcategory_diversity_score + 0.20 * out.specialization_score
    )
    out["activity_score"] = 0.45 * out.sales_density_score + 0.35 * out.transaction_density_score + 0.20 * out.time_fit_score
    out["activity_score_for_ranking"] = np.where(
        out.sales_imputed, 0.50 * out.activity_score + 0.50 * 50.0, out.activity_score
    )
    out["raw_score"] = 0.55 * out.supply_score + 0.35 * out.activity_score_for_ranking + 0.10 * out.access_score
    out["size_adjustment_residual"] = 0.0
    out["size_adjusted_score"] = 0.0
    for _, indices in out.groupby("purpose").groups.items():
        design = np.column_stack([
            np.ones(len(indices)), np.log1p(safe_area.loc[indices]),
            np.log1p(pd.to_numeric(out.loc[indices, "store_count_total"], errors="coerce").fillna(0)),
        ])
        fitted = design @ np.linalg.lstsq(design, out.loc[indices, "raw_score"].to_numpy(), rcond=None)[0]
        residual = out.loc[indices, "raw_score"].to_numpy() - fitted
        out.loc[indices, "size_adjustment_residual"] = residual
        out.loc[indices, "size_adjusted_score"] = _percentile(pd.Series(residual, index=indices))
    tourism = out.area_type_name.eq("관광특구")
    wholesale_shopping = out.purpose.eq("쇼핑") & out.market_channel.eq("도매·전문시장")
    out["recommendation_eligible"] = ~(tourism | wholesale_shopping)
    out["recommendation_exclusion_reason"] = np.select(
        [tourism, wholesale_shopping], ["tourism_special_zone", "wholesale_or_specialized_market"], default=""
    )
    out["rank_eligible"] = out.size_adjusted_score.where(out.recommendation_eligible).groupby(out.purpose).rank(method="min", ascending=False)
    out["recommendation_high_confidence"] = out.recommendation_eligible & out.sales_observed
    out["rank_high_confidence"] = out.size_adjusted_score.where(out.recommendation_high_confidence).groupby(out.purpose).rank(method="min", ascending=False)
    out["recommendation_reason"] = out.apply(_recommendation_reason, axis=1)
    out["quarter"] = quarter
    out = out.sort_values(["purpose", "recommendation_eligible", "rank_eligible", "area_code"], ascending=[True, False, True, True]).reset_index(drop=True)
    audit = {
        "quarter": int(quarter), "area_count": int(out.area_code.nunique()), "row_count": int(len(out)),
        "tourism_special_zone_area_count": int(candidates.area_type_name.eq("관광특구").sum()),
        "wholesale_or_specialized_market_count": int(candidates.market_channel.eq("도매·전문시장").sum()),
        "shopping_sales_observed_area_count": int(out[(out.purpose == "쇼핑") & out.sales_observed].area_code.nunique()),
        "shopping_sales_imputed_area_count": int(out[(out.purpose == "쇼핑") & out.sales_imputed].area_code.nunique()),
        "shopping_high_confidence_area_count": int(out[(out.purpose == "쇼핑") & out.recommendation_high_confidence].area_code.nunique()),
        "meal_high_confidence_area_count": int(out[(out.purpose == "식사") & out.recommendation_high_confidence].area_code.nunique()),
        "adult_or_nightlife_in_meal_score": False,
        "bakery_in_meal_score": False,
        "raw_score_vs_area_km2_pearson": {p: _safe_corr(g.raw_score, g.area_km2) for p, g in out.groupby("purpose")},
        "adjusted_score_vs_area_km2_pearson": {p: _safe_corr(g.size_adjusted_score, g.area_km2) for p, g in out.groupby("purpose")},
        "raw_score_vs_total_stores_pearson": {p: _safe_corr(g.raw_score, g.store_count_total) for p, g in out.groupby("purpose")},
        "adjusted_score_vs_total_stores_pearson": {p: _safe_corr(g.size_adjusted_score, g.store_count_total) for p, g in out.groupby("purpose")},
    }
    return out, detail, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stores", default="data/raw/commercial_area/commercial_store_2025.zip")
    parser.add_argument("--sales", default="data/raw/commercial_area/commercial_sales_2025.zip")
    parser.add_argument("--candidates", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv")
    parser.add_argument("--areas", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    parser.add_argument("--quarter", type=int, default=20254)
    parser.add_argument("--output-dir", default="data/processed/meal_shopping_v1")
    args = parser.parse_args()
    result, detail, audit = build_meal_shopping_v1(
        read_zip_csv(Path(args.stores)), read_zip_csv(Path(args.sales)),
        pd.read_csv(args.candidates, dtype={"area_code": str}), gpd.read_file(args.areas), args.quarter,
    )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / "official_area_meal_shopping_v1_786x2.csv", index=False, encoding="utf-8-sig")
    detail.to_csv(output / "meal_shopping_subcategory_detail_2025q4.csv", index=False, encoding="utf-8-sig")
    high_confidence = result[result.recommendation_high_confidence].sort_values(["purpose", "rank_high_confidence"])
    high_confidence.groupby("purpose", group_keys=False).head(10).to_csv(
        output / "meal_shopping_v1_top10.csv", index=False, encoding="utf-8-sig"
    )
    build_combined_ranking(result).head(10).to_csv(
        output / "meal_plus_shopping_v1_top10.csv", index=False, encoding="utf-8-sig"
    )
    (output / "meal_shopping_v1_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
