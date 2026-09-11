#!/usr/bin/env python3
"""Build leakage-aware PATH-v0 features for accessible official areas."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.build_commercial_area_accessibility import normalize_area_code, read_zip_csv
from scripts.build_purpose_features import PURPOSES, map_industry_to_purpose, purpose_time_columns


def _percentile(values: pd.Series) -> pd.Series:
    values = values.fillna(0.0)
    if values.nunique(dropna=False) <= 1:
        return pd.Series(50.0, index=values.index)
    return values.rank(method="average", pct=True) * 100


def build_features(stores: pd.DataFrame, sales: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    candidates = candidates.copy()
    candidates["area_code"] = candidates["area_code"].map(normalize_area_code)

    stores = stores.copy()
    stores["quarter"] = stores["stdr_yyqu_cd"].astype(int)
    stores["area_code"] = stores["trdar_cd"].map(normalize_area_code)
    stores["purpose"] = stores["svc_induty_cd_nm"].map(map_industry_to_purpose)
    stores = stores[stores.purpose.notna() & stores.area_code.isin(candidates.area_code)]
    store_agg = stores.groupby(["quarter", "area_code", "purpose"], as_index=False).agg(
        purpose_store_count=("stor_co", "sum")
    )

    sales = sales.copy()
    sales["quarter"] = sales["기준_년분기_코드"].astype(int)
    sales["area_code"] = sales["상권_코드"].map(normalize_area_code)
    sales["purpose"] = sales["서비스_업종_코드_명"].map(map_industry_to_purpose)
    sales = sales[sales.purpose.notna() & sales.area_code.isin(candidates.area_code)].copy()
    sales["purpose_time_fit_amount"] = 0.0
    for purpose, indices in sales.groupby("purpose").groups.items():
        cols = [column for column in purpose_time_columns(purpose) if column in sales.columns]
        if cols:
            sales.loc[indices, "purpose_time_fit_amount"] = sales.loc[indices, cols].sum(axis=1)
    sale_agg = sales.groupby(["quarter", "area_code", "purpose"], as_index=False).agg(
        purpose_sales_amount=("당월_매출_금액", "sum"),
        purpose_time_fit_amount=("purpose_time_fit_amount", "sum"),
    )

    quarters = sorted(set(store_agg.quarter) | set(sale_agg.quarter))
    grid = pd.MultiIndex.from_product(
        [quarters, candidates.area_code.unique(), PURPOSES],
        names=["quarter", "area_code", "purpose"],
    ).to_frame(index=False)
    meta = [column for column in [
        "area_code", "area_name", "area_type_name", "primary_admin_name", "primary_district_name",
        "ratio_08", "ratio_14", "ratio_19", "minimum_period_ratio", "mean_period_ratio", "access_tier",
    ] if column in candidates.columns]
    out = grid.merge(candidates[meta].drop_duplicates("area_code"), on="area_code", how="left")
    out = out.merge(store_agg, on=["quarter", "area_code", "purpose"], how="left")
    out = out.merge(sale_agg, on=["quarter", "area_code", "purpose"], how="left")
    measures = ["purpose_store_count", "purpose_sales_amount", "purpose_time_fit_amount"]
    out[measures] = out[measures].fillna(0.0)

    total_stores = out.groupby(["quarter", "area_code"])["purpose_store_count"].transform("sum")
    total_sales = out.groupby(["quarter", "area_code"])["purpose_sales_amount"].transform("sum")
    out["purpose_store_share"] = np.divide(out.purpose_store_count, total_stores, out=np.zeros(len(out)), where=total_stores > 0)
    out["purpose_sales_share"] = np.divide(out.purpose_sales_amount, total_sales, out=np.zeros(len(out)), where=total_sales > 0)
    out["purpose_time_fit_share"] = np.divide(
        out.purpose_time_fit_amount, out.purpose_sales_amount,
        out=np.zeros(len(out)), where=out.purpose_sales_amount > 0,
    )

    groups = ["quarter", "purpose"]
    out["store_count_percentile"] = out.groupby(groups)["purpose_store_count"].transform(lambda x: _percentile(np.log1p(x)))
    out["store_share_percentile"] = out.groupby(groups)["purpose_store_share"].transform(_percentile)
    out["sales_amount_percentile"] = out.groupby(groups)["purpose_sales_amount"].transform(lambda x: _percentile(np.log1p(x)))
    out["sales_share_percentile"] = out.groupby(groups)["purpose_sales_share"].transform(_percentile)
    out["time_fit_percentile"] = out.groupby(groups)["purpose_time_fit_share"].transform(_percentile)
    out["purpose_supply_score"] = 0.65 * out.store_count_percentile + 0.35 * out.store_share_percentile
    out["current_sales_signal"] = (
        0.50 * out.sales_amount_percentile + 0.25 * out.sales_share_percentile + 0.25 * out.time_fit_percentile
    )
    out = out.sort_values(["area_code", "purpose", "quarter"])
    out["lagged_sales_signal"] = out.groupby(["area_code", "purpose"])["current_sales_signal"].shift(1)
    out["path_v0_score"] = 0.70 * out.purpose_supply_score + 0.30 * out.lagged_sales_signal
    out["purpose_rank"] = out.groupby(["quarter", "purpose"])["path_v0_score"].rank(method="min", ascending=False)
    return out.sort_values(["quarter", "purpose", "purpose_rank", "area_code"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stores", type=Path, default=Path("data/raw/commercial_area/commercial_store_2025.zip"))
    parser.add_argument("--sales", type=Path, default=Path("data/raw/commercial_area/commercial_sales_2025.zip"))
    parser.add_argument("--candidates", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/commercial_area_purpose_features"))
    args = parser.parse_args()

    features = build_features(read_zip_csv(args.stores), read_zip_csv(args.sales), pd.read_csv(args.candidates, dtype={"area_code": str}))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output_dir / "official_area_purpose_quarter_features.csv", index=False, encoding="utf-8-sig")
    latest_quarter = int(features.quarter.max())
    latest = features[(features.quarter == latest_quarter) & features.path_v0_score.notna()].copy()
    latest.to_csv(args.output_dir / "official_area_purpose_latest_rankings.csv", index=False, encoding="utf-8-sig")
    latest.groupby("purpose", group_keys=False).head(20).to_csv(
        args.output_dir / "official_area_purpose_top20.csv", index=False, encoding="utf-8-sig"
    )
    report = f"""# 786개 공식 상권 PATH-v0 재산출\n\n- 접근성 25% 탐색 후보: {features.area_code.nunique():,}개\n- 분기·상권·목적 피처: {len(features):,}행\n- 최신 분기: {latest_quarter}\n- 목적: {', '.join(PURPOSES)}\n- 공급 신호: 목적 업종 점포 수 65% + 상권 내 목적 업종 비중 35%\n- 소비 신호: 매출 규모 50% + 목적 매출 비중 25% + 적합 시간대 비중 25%\n- PATH-v0: 공급 신호 70% + 직전 분기 소비 신호 30%\n\n2026년 2분기 행정동 시설 자료는 2025년 순위에 사용하면 미래정보 누출이므로 제외했다. 이 결과는 학습 모형이 아닌 투명한 규칙 기준선이다.\n"""
    (args.output_dir / "PURPOSE_RANKING_REPORT.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
