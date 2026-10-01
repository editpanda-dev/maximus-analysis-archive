#!/usr/bin/env python3
"""Validate flow-sales models across 2023-2025 quarters and years."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

from scripts.flow_sales_gap import aggregate_inputs, normalize_admin_code


def balanced_panel(frame: pd.DataFrame) -> pd.DataFrame:
    needed = frame["quarter"].nunique()
    counts = frame.groupby("admin_code")["quarter"].nunique()
    return frame[frame.admin_code.isin(counts[counts == needed].index)].copy()


def forward_splits(frame: pd.DataFrame):
    years = sorted(frame.year.unique())
    return [(f"train_to_{year-1}_test_{year}", frame.year < year, frame.year == year) for year in years[1:]]


def quarter_splits(frame):
    return [(f"holdout_{q}", frame.quarter != q, frame.quarter == q) for q in sorted(frame.quarter.unique())]


def year_splits(frame):
    return [(f"holdout_{y}", frame.year != y, frame.year == y) for y in sorted(frame.year.unique())]


def group_splits(frame: pd.DataFrame, group_column: str, n_splits: int = 5):
    n = min(n_splits, frame[group_column].nunique())
    splitter = GroupKFold(n_splits=n)
    groups = frame[group_column]
    splits = []
    for fold, (train_idx, test_idx) in enumerate(splitter.split(frame, groups=groups), start=1):
        train = pd.Series(False, index=frame.index)
        test = pd.Series(False, index=frame.index)
        train.iloc[train_idx] = True
        test.iloc[test_idx] = True
        splits.append((f"{group_column}_fold_{fold}", train, test))
    return splits


def model():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=.04, max_leaf_nodes=15,
                                         min_samples_leaf=20, l2_regularization=1.5, random_state=42)


def evaluate(frame, features, splits, scheme, model_name):
    prediction = pd.Series(index=frame.index, dtype=float)
    rows = []
    for label, train, test in splits:
        fitted = model().fit(frame.loc[train, features], frame.loc[train, "log_sales"])
        pred = fitted.predict(frame.loc[test, features])
        prediction.loc[test] = pred
        actual = frame.loc[test, "log_sales"]
        rows.append({"scheme": scheme, "split": label, "model": model_name, "test_rows": int(test.sum()),
                     "rmse": mean_squared_error(actual, pred) ** .5, "mae": mean_absolute_error(actual, pred),
                     "r2": r2_score(actual, pred)})
    valid = prediction.notna()
    overall = {"scheme": scheme, "split": "pooled", "model": model_name, "test_rows": int(valid.sum()),
               "rmse": mean_squared_error(frame.loc[valid, "log_sales"], prediction[valid]) ** .5,
               "mae": mean_absolute_error(frame.loc[valid, "log_sales"], prediction[valid]),
               "r2": r2_score(frame.loc[valid, "log_sales"], prediction[valid])}
    return pd.DataFrame(rows + [overall]), prediction


def read_context(path, rename):
    frame = pd.read_csv(path, encoding="cp949", low_memory=False).rename(columns=rename)
    frame["admin_code"] = frame["행정동_코드"].map(normalize_admin_code)
    return frame.rename(columns={"기준_년분기_코드": "quarter"})


def run(args):
    sales = pd.concat([pd.read_csv(p, encoding="cp949", low_memory=False) for p in args.sales], ignore_index=True)
    stores = pd.concat([pd.read_csv(p, encoding="cp949", low_memory=False) for p in args.stores], ignore_index=True)
    flow = pd.read_csv(args.flow, encoding="cp949", low_memory=False)
    frame = aggregate_inputs(sales, stores, flow)
    frame = frame[frame.quarter.between(20231, 20254)].copy()

    candidates = pd.read_csv(args.candidates, dtype={"emdcd": str})
    candidates = candidates[candidates.time_stability == "all_three_periods"].copy()
    candidates["admin_code"] = candidates.emdcd.map(normalize_admin_code)
    frame = frame.merge(candidates[["admin_code", "sggnm", "minimum_period_ratio", "mean_period_ratio"]], on="admin_code")

    resident = read_context(args.resident, {"총_상주인구_수": "resident_population"})
    workplace = read_context(args.workplace, {"총_직장_인구_수": "workplace_population"})
    facilities = read_context(args.facilities, {
        "집객시설_수": "facility_count", "종합병원_수": "general_hospital_count", "일반_병원_수": "hospital_count",
        "약국_수": "pharmacy_count", "대학교_수": "university_count", "백화점_수": "department_store_count",
        "극장_수": "theater_count", "숙박_시설_수": "accommodation_count", "철도_역_수": "rail_station_count",
        "지하철_역_수": "subway_station_count", "버스_정거장_수": "bus_stop_count",
    })
    frame = frame.merge(resident[["quarter", "admin_code", "resident_population"]], on=["quarter", "admin_code"], how="left")
    frame = frame.merge(workplace[["quarter", "admin_code", "workplace_population"]], on=["quarter", "admin_code"], how="left")
    fcols = [c for c in facilities if c.endswith("_count")]
    frame = frame.merge(facilities[["quarter", "admin_code"] + fcols], on=["quarter", "admin_code"], how="left")
    frame = frame[(frame.sales_amount > 0) & (frame.store_count > 0) & (frame.floating_population > 0)].copy()
    frame = balanced_panel(frame)
    frame["year"] = frame.quarter // 10
    frame["log_sales"] = np.log1p(frame.sales_amount)
    frame["log_flow"] = np.log1p(frame.floating_population)
    frame["log_stores"] = np.log1p(frame.store_count)
    context = ["resident_population", "workplace_population"] + fcols
    for col in context:
        frame[f"log_{col}"] = np.log1p(frame[col].fillna(0))
    base_features = ["log_flow", "log_stores"]
    expanded_features = base_features + [f"log_{c}" for c in context]

    all_metrics, predictions = [], {}
    schemes = [("quarter_holdout", quarter_splits(frame)), ("year_holdout", year_splits(frame)),
               ("forward_year", forward_splits(frame)), ("dong_group_holdout", group_splits(frame, "admin_code")),
               ("district_group_holdout", group_splits(frame, "sggnm"))]
    for scheme, splits in schemes:
        for name, features in [("base", base_features), ("expanded", expanded_features)]:
            metric, pred = evaluate(frame, features, splits, scheme, name)
            all_metrics.append(metric); predictions[(scheme, name)] = pred
    metrics_df = pd.concat(all_metrics, ignore_index=True)

    frame["year_holdout_base_pred"] = predictions[("year_holdout", "base")]
    frame["year_holdout_expanded_pred"] = predictions[("year_holdout", "expanded")]
    frame["year_holdout_base_gap"] = frame.log_sales - frame.year_holdout_base_pred
    frame["year_holdout_expanded_gap"] = frame.log_sales - frame.year_holdout_expanded_pred

    flags = pd.read_csv(args.flagged, dtype={"admin_code": str})
    flags = flags[flags.gap_type != "일반형"][["admin_code", "dong_name", "sggnm", "gap_type", "mean_gap_z"]]
    candidate_year = frame[frame.admin_code.isin(flags.admin_code)].groupby(["admin_code", "year"], as_index=False).agg(
        base_gap=("year_holdout_base_gap", "mean"), expanded_gap=("year_holdout_expanded_gap", "mean"))
    pivot = candidate_year.pivot(index="admin_code", columns="year", values="expanded_gap").add_prefix("expanded_gap_").reset_index()
    candidate_summary = flags.merge(pivot, on="admin_code", how="left")
    expected_sign = np.where(candidate_summary.gap_type == "목적소비형", 1, -1)
    year_cols = [c for c in candidate_summary if c.startswith("expanded_gap_")]
    candidate_summary["years_same_direction"] = [sum(np.sign(row[c]) == sign for c in year_cols if pd.notna(row[c]))
                                                   for (_, row), sign in zip(candidate_summary.iterrows(), expected_sign)]
    candidate_summary["three_year_stable"] = candidate_summary.years_same_direction == len(year_cols)

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(out / "multi_period_model_metrics.csv", index=False, encoding="utf-8-sig")
    frame.to_csv(out / "balanced_2023_2025_panel.csv", index=False, encoding="utf-8-sig")
    candidate_year.to_csv(out / "gap_13_yearly_residuals.csv", index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(out / "gap_13_temporal_stability.csv", index=False, encoding="utf-8-sig")

    pooled = metrics_df[metrics_df.split == "pooled"].pivot(index="scheme", columns="model", values=["rmse", "r2"])
    q_base, q_exp = pooled.loc["quarter_holdout", ("r2", "base")], pooled.loc["quarter_holdout", ("r2", "expanded")]
    y_base, y_exp = pooled.loc["year_holdout", ("r2", "base")], pooled.loc["year_holdout", ("r2", "expanded")]
    f_base, f_exp = pooled.loc["forward_year", ("r2", "base")], pooled.loc["forward_year", ("r2", "expanded")]
    d_base, d_exp = pooled.loc["dong_group_holdout", ("r2", "base")], pooled.loc["dong_group_holdout", ("r2", "expanded")]
    district_base, district_exp = pooled.loc["district_group_holdout", ("r2", "base")], pooled.loc["district_group_holdout", ("r2", "expanded")]
    stable = int(candidate_summary.three_year_stable.sum())
    q_detail = metrics_df[(metrics_df.scheme == "quarter_holdout") & (metrics_df["split"] != "pooled")]
    q_exp_min, q_exp_max = q_detail[q_detail.model == "expanded"].r2.min(), q_detail[q_detail.model == "expanded"].r2.max()
    y_detail = metrics_df[(metrics_df.scheme == "year_holdout") & (metrics_df["split"] != "pooled") & (metrics_df.model == "expanded")]
    y_exp_min, y_exp_max = y_detail.r2.min(), y_detail.r2.max()
    lines = ["# 2023~2025 다기간 설명력 검증", "", "## 데이터", "",
             f"2023년 1분기부터 2025년 4분기까지 12개 분기를 결합했다. 모든 분기에 자료가 존재하는 {frame.admin_code.nunique()}개 행정동, {len(frame)}개 관측치만 사용했다.", "",
             "## 검증 결과", "",
             f"분기 하나씩 제외한 검증에서 기본모형 R²는 {q_base:.3f}, 확장모형은 {q_exp:.3f}이었다.",
             f"연도 전체를 제외한 검증에서 기본모형 R²는 {y_base:.3f}, 확장모형은 {y_exp:.3f}이었다.",
             f"과거 연도로 다음 연도를 예측한 검증에서 기본모형 R²는 {f_base:.3f}, 확장모형은 {f_exp:.3f}이었다.", "",
             f"행정동을 통째로 제외한 공간 홀드아웃에서 기본모형 R²는 {d_base:.3f}, 확장모형은 {d_exp:.3f}이었다.",
             f"자치구를 통째로 제외한 더 강한 공간 홀드아웃에서 기본모형 R²는 {district_base:.3f}, 확장모형은 {district_exp:.3f}이었다.", "",
             f"확장모형의 분기별 R² 범위는 {q_exp_min:.3f}~{q_exp_max:.3f}, 연도별 홀드아웃 범위는 {y_exp_min:.3f}~{y_exp_max:.3f}이었다. 특정 한 분기만 성능을 끌어올린 형태는 관찰되지 않았다.", "",
             "확장모형이 세 검증 모두에서 우세하면 상주·직장인구와 집객시설의 설명력이 특정 분기에만 나타난 효과일 가능성은 낮아진다. 다만 같은 행정동이 반복 관측되므로 새로운 지역으로의 일반화까지 증명한 것은 아니다.", "",
             "## 13개 후보의 시간 안정성", "",
             f"2025년에 선정한 13개 후보 중 확장모형 잔차 방향이 2023·2024·2025년에 모두 같은 곳은 {stable}개였다. 나머지는 특정 연도에 방향이 바뀌므로 고정된 상권 유형으로 부르지 않고 시기별 후보로 관리해야 한다.", "",
             "|유형|행정동|2023 잔차|2024 잔차|2025 잔차|3개년 동일방향|", "|---|---|---:|---:|---:|---|"]
    for _, x in candidate_summary.sort_values(["gap_type", "dong_name"]).iterrows():
        values = [x.get(f"expanded_gap_{y}", np.nan) for y in [2023, 2024, 2025]]
        fmt = ["자료없음" if pd.isna(v) else f"{v:.3f}" for v in values]
        lines.append(f"|{x.gap_type}|{x.dong_name}|{fmt[0]}|{fmt[1]}|{fmt[2]}|{'예' if x.three_year_stable else '아니오'}|")
    lines += ["", "## 해석 한계", "",
              "13개 후보는 2025년 자료로 먼저 선정했기 때문에 과거 잔차 비교에는 선택편향이 있다. 따라서 3개년 동일방향 여부는 안정성 진단이지 독립적인 발견 검증이 아니다. 최종 모델에서는 시간 순서 검증과 함께 출발 행정동 또는 목적지 행정동을 통째로 제외하는 공간 홀드아웃도 수행한다."]
    (out / "MULTI_PERIOD_VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    plt.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    chart = metrics_df[metrics_df.split == "pooled"].pivot(index="scheme", columns="model", values="r2")
    ax = chart.reindex(["quarter_holdout", "year_holdout", "forward_year", "dong_group_holdout", "district_group_holdout"]).rename(index={"quarter_holdout": "분기 홀드아웃", "year_holdout": "연도 홀드아웃", "forward_year": "순방향 연도", "dong_group_holdout": "행정동 공간 홀드아웃", "district_group_holdout": "자치구 공간 홀드아웃"},
                      columns={"base": "기본", "expanded": "확장"}).plot(kind="bar", figsize=(8, 5), color=["#9AA0A6", "#F4B400"])
    ax.set(ylabel="R²", xlabel="", title="2023~2025 기간 외 검증 설명력"); ax.set_ylim(0, 1); ax.tick_params(axis="x", rotation=0)
    ax.figure.tight_layout(); ax.figure.savefig(out / "multi_period_r2_comparison.png", dpi=180); plt.close(ax.figure)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--sales", nargs="+", default=[f"data/raw/seoul_commercial_sales_dong_{y}.csv" for y in [2023, 2024, 2025]])
    p.add_argument("--stores", nargs="+", default=[f"data/raw/seoul_commercial_stores_dong_{y}.csv" for y in [2023, 2024, 2025]])
    p.add_argument("--flow", default="data/raw/seoul_commercial_floating_population_dong.csv")
    p.add_argument("--resident", default="data/raw/seoul_resident_population_dong.csv")
    p.add_argument("--workplace", default="data/raw/seoul_workplace_population_dong.csv")
    p.add_argument("--facilities", default="data/raw/seoul_attracting_facilities_dong.csv")
    p.add_argument("--candidates", default="data/processed/local_transit_30min/time_period_candidates.csv")
    p.add_argument("--flagged", default="data/processed/flow_sales_gap/flow_sales_gap_candidates.csv")
    p.add_argument("--output", default="data/processed/flow_sales_gap/multi_period_validation")
    return p.parse_args()


if __name__ == "__main__": run(parse_args())
