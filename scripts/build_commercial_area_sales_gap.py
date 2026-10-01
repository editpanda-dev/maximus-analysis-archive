#!/usr/bin/env python3
"""Diagnose 2025 sales gaps for the 786 accessible official commercial areas.

This is intentionally a *sales-structure* baseline, not a floating-population
model.  The matching official-area floating-population Open API is not present
in the local archive, so no administrative-dong proxy or future-quarter value
is substituted here.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_commercial_area_accessibility import (
    load_areas,
    normalize_area_code,
    read_zip_csv,
)


def _entropy(values: pd.Series) -> float:
    shares = values[values > 0] / values.sum()
    return float(-(shares * np.log(shares)).sum()) if not shares.empty else 0.0


def build_gap_features(stores: pd.DataFrame, sales: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    """Return a quarter-area panel of sales and non-leaking structural features."""
    meta = candidates.copy()
    meta["area_code"] = meta["area_code"].map(normalize_area_code)
    required = {"area_code", "area_name", "area_type_name", "area_m2"}
    missing = required - set(meta.columns)
    if missing:
        raise ValueError(f"Candidate metadata missing: {sorted(missing)}")
    meta = meta[["area_code", "area_name", "area_type_name", "area_m2"]].drop_duplicates("area_code")

    stores = stores.copy()
    stores["quarter"] = stores["stdr_yyqu_cd"].astype(int)
    stores["area_code"] = stores["trdar_cd"].map(normalize_area_code)
    stores = stores[stores.area_code.isin(meta.area_code)]
    store_total = stores.groupby(["quarter", "area_code"], as_index=False)["stor_co"].sum().rename(
        columns={"stor_co": "store_count"}
    )
    entropy = stores.groupby(["quarter", "area_code"])["stor_co"].apply(_entropy).rename("industry_entropy").reset_index()

    sales = sales.copy()
    sales["quarter"] = sales["기준_년분기_코드"].astype(int)
    sales["area_code"] = sales["상권_코드"].map(normalize_area_code)
    sales = sales[sales.area_code.isin(meta.area_code)]
    sales_total = sales.groupby(["quarter", "area_code"], as_index=False)["당월_매출_금액"].sum().rename(
        columns={"당월_매출_금액": "sales_amount"}
    )

    quarters = sorted(set(stores.quarter) | set(sales.quarter))
    grid = pd.MultiIndex.from_product([quarters, meta.area_code], names=["quarter", "area_code"]).to_frame(index=False)
    out = grid.merge(meta, on="area_code", how="left").merge(store_total, on=["quarter", "area_code"], how="left")
    out = out.merge(entropy, on=["quarter", "area_code"], how="left").merge(sales_total, on=["quarter", "area_code"], how="left")
    out[["store_count", "industry_entropy", "sales_amount"]] = out[["store_count", "industry_entropy", "sales_amount"]].fillna(0.0)
    out["log_store_count"] = np.log1p(out.store_count)
    out["log_area_m2"] = np.log1p(out.area_m2.clip(lower=0))
    out["log_sales"] = np.log1p(out.sales_amount.clip(lower=0))
    return out.sort_values(["quarter", "area_code"]).reset_index(drop=True)


def _design_matrix(panel: pd.DataFrame) -> pd.DataFrame:
    numeric = panel[["log_store_count", "log_area_m2", "industry_entropy"]].copy()
    type_dummies = pd.get_dummies(panel["area_type_name"], prefix="area_type", dtype=float)
    quarter_dummies = pd.get_dummies(panel["quarter"].astype(str), prefix="quarter", dtype=float)
    return pd.concat([numeric, type_dummies, quarter_dummies], axis=1)


def evaluate_models(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create out-of-fold predictions by quarter and by unseen commercial area."""
    X = _design_matrix(panel)
    y = panel.log_sales.to_numpy()
    records: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    split_specs: list[tuple[str, list[tuple[np.ndarray, np.ndarray]]]] = []
    q_splits = []
    for quarter in sorted(panel.quarter.unique()):
        test = np.where(panel.quarter.to_numpy() == quarter)[0]
        train = np.where(panel.quarter.to_numpy() != quarter)[0]
        q_splits.append((train, test))
    split_specs.append(("quarter_holdout", q_splits))
    groups = panel.area_code.to_numpy()
    split_specs.append(("spatial_group_holdout", list(GroupKFold(n_splits=5).split(X, y, groups))))

    for split_name, splits in split_specs:
        for model_name, factory in {
            "ridge": lambda: Ridge(alpha=5.0),
            "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(
                learning_rate=0.06, max_leaf_nodes=15, l2_regularization=1.0, random_state=42
            ),
        }.items():
            oof = np.full(len(panel), np.nan)
            for train_idx, test_idx in splits:
                model = factory()
                model.fit(X.iloc[train_idx], y[train_idx])
                oof[test_idx] = model.predict(X.iloc[test_idx])
            records.append({"validation": split_name, "model": model_name, "log_sales_r2": r2_score(y, oof)})
            if split_name == "quarter_holdout" and model_name == "hist_gradient_boosting":
                frame = panel[["quarter", "area_code"]].copy()
                frame["expected_log_sales"] = oof
                prediction_frames.append(frame)
    predictions = prediction_frames[0] if prediction_frames else pd.DataFrame()
    return pd.DataFrame(records), predictions


def classify_persistent_gaps(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out["log_residual"] = out.log_sales - out.expected_log_sales
    out["residual_z"] = out.groupby("quarter")["log_residual"].transform(
        lambda x: (x - x.mean()) / x.std(ddof=0) if x.std(ddof=0) else 0.0
    )
    out["gap_direction"] = np.select(
        [out.residual_z >= 1.0, out.residual_z <= -1.0], ["above_expected", "below_expected"], default="within_expected"
    )
    summary = out.groupby(["area_code", "area_name", "area_type_name"], as_index=False).agg(
        evaluated_quarters=("quarter", "nunique"),
        above_expected_quarters=("gap_direction", lambda x: int((x == "above_expected").sum())),
        below_expected_quarters=("gap_direction", lambda x: int((x == "below_expected").sum())),
        mean_residual_z=("residual_z", "mean"),
        mean_actual_to_expected_log_gap=("log_residual", "mean"),
    )
    summary["persistent_gap"] = np.select(
        [summary.above_expected_quarters >= 3, summary.below_expected_quarters >= 3],
        ["persistently_above_expected", "persistently_below_expected"], default="not_persistent",
    )
    return out, summary.sort_values(["persistent_gap", "mean_residual_z"], ascending=[True, False]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--areas", type=Path, default=Path("data/raw/commercial_area/commercial_area.zip"))
    parser.add_argument("--stores", type=Path, default=Path("data/raw/commercial_area/commercial_store_2025.zip"))
    parser.add_argument("--sales", type=Path, default=Path("data/raw/commercial_area/commercial_sales_2025.zip"))
    parser.add_argument("--candidates", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/commercial_area_sales_gap"))
    args = parser.parse_args()

    candidates = pd.read_csv(args.candidates, dtype={"area_code": str})
    area_m2 = load_areas(args.areas).assign(area_m2=lambda x: x.geometry.area)[["area_code", "area_m2"]]
    candidates = candidates.merge(area_m2, on="area_code", how="left")
    panel = build_gap_features(read_zip_csv(args.stores), read_zip_csv(args.sales), candidates)
    metrics, predictions = evaluate_models(panel)
    panel = panel.merge(predictions, on=["quarter", "area_code"], how="left")
    panel, gaps = classify_persistent_gaps(panel)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output_dir / "official_area_sales_structure_gap_quarter.csv", index=False, encoding="utf-8-sig")
    gaps.to_csv(args.output_dir / "official_area_sales_structure_gap_candidates.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(args.output_dir / "model_comparison.csv", index=False, encoding="utf-8-sig")
    persistent = gaps[gaps.persistent_gap != "not_persistent"]
    report = f"""# 786개 공식 상권 매출 구조 괴리 분석\n\n- 분석 단위: 25% 접근성 후보 공식 상권 {panel.area_code.nunique():,}개 × 2025년 4개 분기\n- 기대매출 입력: 점포 수, 상권 면적, 점포 업종 다양성, 상권 유형\n- 목표값: 로그 변환 월 매출액\n- 검증: 분기 홀드아웃(같은 상권의 다른 분기는 학습에 포함)과 상권 그룹 홀드아웃(처음 보는 상권)\n- 지속 괴리: 4개 분기 중 3개 이상에서 분기 내 잔차 Z값이 +1 또는 -1을 넘는 상권\n- 지속 괴리 후보: {len(persistent):,}개\n\n## 해석 제한\n\n이 결과는 **유동인구–매출 괴리 분석이 아니다**. 공식 상권 단위 유동인구 원본이 아직 로컬에 없어, 행정동 유동인구 또는 미래 분기 자료를 대체값으로 섞지 않았다. 따라서 이 결과는 ‘점포 구조와 면적으로 예상한 매출에서 반복적으로 벗어나는 상권’을 후속 조사 대상으로 선별하는 보조 진단이며, 사용자에게 ‘쇼핑하기 좋다’를 직접 판정하거나 추천 성능으로 주장하지 않는다.\n"""
    (args.output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
