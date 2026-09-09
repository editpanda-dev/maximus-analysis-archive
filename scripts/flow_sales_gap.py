#!/usr/bin/env python3
"""Build a quarter-by-dong flow/sales gap table from Seoul public data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def normalize_admin_code(value) -> str:
    digits = "".join(ch for ch in str(value).split(".")[0] if ch.isdigit())
    if len(digits) >= 10:
        digits = digits[:8]
    return digits.zfill(8)


def purpose_group(service_name: str) -> str:
    name = str(service_name)
    if name == "커피-음료":
        return "카페"
    if any(word in name for word in ["음식점", "분식", "치킨", "패스트푸드", "제과점", "반찬"]):
        return "식사"
    if any(word in name for word in ["서적", "문구", "독서", "교습학원", "외국어학원", "예술학원"]):
        return "공부"
    if any(word in name for word in ["의류", "가방", "신발", "화장품", "귀금속", "슈퍼마켓", "편의점", "판매", "가구", "가전", "안경", "완구", "화초", "용품", "청과", "미곡", "수산", "육류"]):
        return "쇼핑"
    if any(word in name for word in ["노래방", "PC방", "당구장", "골프", "스포츠", "클럽", "주점", "여관"]):
        return "여가문화"
    return "생활서비스"


def aggregate_inputs(sales: pd.DataFrame, stores: pd.DataFrame, flow: pd.DataFrame) -> pd.DataFrame:
    keys = ["기준_년분기_코드", "행정동_코드"]
    sales_agg = sales.groupby(keys, as_index=False).agg(
        dong_name=("행정동_코드_명", "first"),
        sales_amount=("당월_매출_금액", "sum"),
        sales_count=("당월_매출_건수", "sum"),
    )
    stores_agg = stores.groupby(keys, as_index=False).agg(
        store_count=("점포_수", "sum"),
        similar_store_count=("유사_업종_점포_수", "sum"),
    )
    flow_agg = flow.groupby(keys, as_index=False).agg(
        floating_population=("총_유동인구_수", "sum"),
    )
    out = sales_agg.merge(stores_agg, on=keys, how="inner").merge(flow_agg, on=keys, how="inner")
    out = out.rename(columns={"기준_년분기_코드": "quarter", "행정동_코드": "admin_code"})
    out["admin_code"] = out["admin_code"].map(normalize_admin_code)
    return out.sort_values(["quarter", "admin_code"]).reset_index(drop=True)


def classify_persistent_gap(frame: pd.DataFrame, threshold: float = 1.0, min_quarters: int = 3) -> pd.DataFrame:
    rows = []
    for code, group in frame.groupby("admin_code"):
        positive = int((group["gap_z"] >= threshold).sum())
        negative = int((group["gap_z"] <= -threshold).sum())
        if positive >= min_quarters:
            label = "목적소비형"
        elif negative >= min_quarters:
            label = "통과형"
        else:
            label = "일반형"
        row = {
            "admin_code": code,
            "quarters_observed": len(group),
            "positive_gap_quarters": positive,
            "negative_gap_quarters": negative,
            "mean_gap_z": group["gap_z"].mean(),
            "mean_gap_ratio": group["gap_ratio"].mean() if "gap_ratio" in group else np.nan,
            "gap_type": label,
        }
        for col in ["dong_name", "sggnm", "minimum_period_ratio", "mean_period_ratio"]:
            if col in group:
                row[col] = group[col].iloc[0]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("mean_gap_z", ascending=False).reset_index(drop=True)


def _make_model(kind: str):
    if kind == "linear":
        prep = ColumnTransformer([
            ("numeric", StandardScaler(), ["log_flow", "log_stores"]),
            ("quarter", OneHotEncoder(handle_unknown="ignore"), ["quarter_text"]),
        ])
        return make_pipeline(prep, Ridge(alpha=1.0))
    return HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, max_leaf_nodes=15,
                                         min_samples_leaf=20, l2_regularization=1.0,
                                         random_state=42)


def cross_validated_predictions(frame: pd.DataFrame, kind: str) -> np.ndarray:
    features = ["log_flow", "log_stores", "quarter_text"] if kind == "linear" else ["log_flow", "log_stores", "quarter_index"]
    predictions = pd.Series(index=frame.index, dtype=float)
    for quarter in sorted(frame["quarter"].unique()):
        train = frame["quarter"] != quarter
        test = ~train
        model = _make_model(kind)
        model.fit(frame.loc[train, features], frame.loc[train, "log_sales"])
        predictions.loc[test] = model.predict(frame.loc[test, features])
    return predictions.to_numpy()


def score_predictions(actual: pd.Series, predicted: np.ndarray) -> dict:
    return {
        "rmse_log_sales": float(mean_squared_error(actual, predicted) ** 0.5),
        "mae_log_sales": float(mean_absolute_error(actual, predicted)),
        "r2_log_sales": float(r2_score(actual, predicted)),
    }


def save_charts(frame: pd.DataFrame, summary: pd.DataFrame, comparison: pd.DataFrame, out: Path) -> None:
    plt.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    colors = frame["gap_z"].clip(-3, 3)
    scatter = ax.scatter(frame["log_flow"], frame["log_sales"], c=colors, cmap="RdYlBu_r", alpha=.72, s=24)
    ax.set(xlabel="log(유동인구+1)", ylabel="log(매출+1)", title="유동인구가 같아도 매출 잔차는 다르게 나타남")
    fig.colorbar(scatter, ax=ax, label="분기 내 매출 괴리 z")
    fig.tight_layout()
    fig.savefig(out / "flow_sales_gap_scatter.png", dpi=180)
    plt.close(fig)

    flagged = summary[summary["gap_type"] != "일반형"].sort_values("mean_gap_z")
    fig, ax = plt.subplots(figsize=(8.0, 5.5))
    ax.barh(flagged["dong_name"], flagged["mean_gap_z"],
            color=np.where(flagged["mean_gap_z"] > 0, "#F4B400", "#5F6368"))
    ax.axvline(0, color="#222", lw=.8)
    ax.set(xlabel="4개 분기 평균 괴리 z", title="반복적으로 기대매출을 벗어난 후보지")
    fig.tight_layout()
    fig.savefig(out / "persistent_gap_candidates.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.bar(comparison["model"], comparison["rmse_log_sales"], color=["#F4B400", "#9AA0A6"])
    ax.set(ylabel="분기 홀드아웃 RMSE (낮을수록 좋음)", title="선형 대 비선형 기대매출 모형")
    for idx, value in enumerate(comparison["rmse_log_sales"]):
        ax.text(idx, value + .008, f"{value:.3f}", ha="center")
    fig.tight_layout()
    fig.savefig(out / "model_comparison.png", dpi=180)
    plt.close(fig)


def run(args) -> None:
    read = lambda path: pd.read_csv(path, encoding="cp949", low_memory=False)
    sales_raw, stores_raw, flow_raw = read(args.sales), read(args.stores), read(args.flow)
    frame = aggregate_inputs(sales_raw, stores_raw, flow_raw)
    frame = frame[(frame["quarter"] >= 20251) & (frame["quarter"] <= 20254)].copy()

    candidates = pd.read_csv(args.candidates, dtype={"emdcd": str})
    candidates["admin_code"] = candidates["emdcd"].map(normalize_admin_code)
    candidates = candidates[candidates["time_stability"] == "all_three_periods"].copy()
    keep = ["admin_code", "sggnm", "minimum_period_ratio", "mean_period_ratio"]
    frame = frame.merge(candidates[keep], on="admin_code", how="inner")
    frame = frame[(frame["sales_amount"] > 0) & (frame["store_count"] > 0) & (frame["floating_population"] > 0)].copy()
    frame["log_sales"] = np.log1p(frame["sales_amount"])
    frame["log_flow"] = np.log1p(frame["floating_population"])
    frame["log_stores"] = np.log1p(frame["store_count"])
    frame["quarter_text"] = frame["quarter"].astype(str)
    frame["quarter_index"] = frame["quarter"] - frame["quarter"].min()

    comparisons = []
    predictions = {}
    for kind in ["linear", "nonlinear"]:
        pred = cross_validated_predictions(frame, kind)
        predictions[kind] = pred
        comparisons.append({"model": kind, **score_predictions(frame["log_sales"], pred)})
    comparison = pd.DataFrame(comparisons).sort_values("rmse_log_sales").reset_index(drop=True)
    chosen = comparison.iloc[0]["model"]
    frame["predicted_log_sales"] = predictions[chosen]
    frame["predicted_sales"] = np.expm1(frame["predicted_log_sales"]).clip(lower=0)
    frame["gap_log"] = frame["log_sales"] - frame["predicted_log_sales"]
    frame["gap_ratio"] = frame["sales_amount"] / frame["predicted_sales"].replace(0, np.nan)
    frame["gap_z"] = frame.groupby("quarter")["gap_log"].transform(
        lambda x: (x - x.mean()) / x.std(ddof=0) if x.std(ddof=0) else 0.0
    )

    summary = classify_persistent_gap(frame)
    latest = frame.sort_values("quarter").groupby("admin_code", as_index=False).tail(1)
    summary = summary.merge(latest[["admin_code", "sales_amount", "floating_population", "store_count"]],
                            on="admin_code", how="left")
    flow_floor = float(latest["floating_population"].quantile(0.05))
    store_floor = float(latest["store_count"].quantile(0.05))
    summary["data_quality_warning"] = np.where(
        (summary["floating_population"] < flow_floor) | (summary["store_count"] < store_floor),
        "하위 5% 규모: 잔차 과장 가능", ""
    )

    # Explain flagged dongs using the latest-quarter service composition.
    sales_profile = sales_raw[sales_raw["기준_년분기_코드"] == 20254].copy()
    sales_profile["admin_code"] = sales_profile["행정동_코드"].map(normalize_admin_code)
    sales_profile["purpose"] = sales_profile["서비스_업종_코드_명"].map(purpose_group)
    sales_profile = sales_profile.groupby(["admin_code", "purpose"], as_index=False)["당월_매출_금액"].sum()
    totals = sales_profile.groupby("admin_code")["당월_매출_금액"].transform("sum")
    sales_profile["sales_share"] = sales_profile["당월_매출_금액"] / totals
    purpose_wide = sales_profile.pivot(index="admin_code", columns="purpose", values="sales_share").fillna(0).reset_index()
    purpose_wide.columns.name = None
    summary = summary.merge(purpose_wide, on="admin_code", how="left")

    top_industries = sales_raw[sales_raw["기준_년분기_코드"] == 20254].copy()
    top_industries["admin_code"] = top_industries["행정동_코드"].map(normalize_admin_code)
    top_industries = top_industries.sort_values("당월_매출_금액", ascending=False).groupby("admin_code").head(3)
    top_industries = top_industries.groupby("admin_code")["서비스_업종_코드_명"].agg(" · ".join).rename("top_3_industries")
    summary = summary.merge(top_industries, on="admin_code", how="left")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "candidate_dong_features.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "flow_sales_gap_candidates.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(out / "model_comparison.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "chosen_model": chosen,
        "candidate_dongs": int(frame["admin_code"].nunique()),
        "observations": int(len(frame)),
        "quarters": sorted(int(x) for x in frame["quarter"].unique()),
        "purpose_consumption_dongs": int((summary["gap_type"] == "목적소비형").sum()),
        "pass_through_dongs": int((summary["gap_type"] == "통과형").sum()),
        "interpretation_limit": "Association and prediction only; residuals do not establish causality.",
    }
    (out / "run_summary.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    save_charts(frame, summary, comparison, out)

    flagged = summary[summary["gap_type"] != "일반형"]
    lines = [
        "# 동대문구 출발 30분 후보지 유동–매출 괴리 EDA",
        "",
        "## 분석 결론",
        "",
        f"2025년 4개 분기, 접근성이 세 시간대 모두 안정적인 후보 {metadata['candidate_dongs']}개를 분석했다. "
        f"분기 단위 교차검증에서 비선형모형의 로그매출 R²는 {comparison.iloc[0]['r2_log_sales']:.3f}, "
        f"선형모형은 {comparison.iloc[1]['r2_log_sales']:.3f}이었다. 따라서 유동인구와 매출의 관계를 단일 직선으로만 보는 것은 부족하다.",
        "",
        f"유동인구와 점포 수로 기대되는 매출보다 1 표준편차 이상 높은 상태가 3개 분기 이상 반복된 목적소비형은 {metadata['purpose_consumption_dongs']}개, "
        f"낮은 상태가 반복된 통과형은 {metadata['pass_through_dongs']}개였다. 이는 원인 판정이 아니라 후속 조사 후보 선별 결과다.",
        "",
        "## 판정 방법",
        "",
        "총매출·유동인구·점포 수를 로그 변환하고 분기 효과를 반영했다. 선형 Ridge와 비선형 HistGradientBoosting을 각 분기 홀드아웃 방식으로 비교한 뒤 더 낮은 RMSE 모형의 교차검증 예측값을 기대매출로 사용했다. 실제 로그매출과 기대 로그매출의 차이를 분기별 표준화하여 괴리지수로 만들었다.",
        "",
        "## 반복 괴리 후보",
        "",
        "|유형|행정동|자치구|평균 괴리 z|실제/기대 매출|상위 업종|주의|",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for _, row in flagged.sort_values(["gap_type", "mean_gap_z"], ascending=[True, False]).iterrows():
        lines.append(f"|{row.gap_type}|{row.dong_name}|{row.sggnm}|{row.mean_gap_z:.2f}|{row.mean_gap_ratio:.2f}|{row.top_3_industries}|{row.data_quality_warning}|")
    lines += [
        "",
        "## 해석상 주의",
        "",
        "둔촌1동처럼 유동인구 또는 점포 규모가 매우 작은 지역은 비율과 잔차가 커질 수 있어 현장·지도·재개발 상태를 별도 확인해야 한다. 2026년 행정동 경계의 용두동·신설동은 2025년 상권자료 코드와 일치하지 않아 이번 결합에서 제외되었다. 또한 길단위 유동인구는 B078의 방문목적 이동량과 다르므로, 목적을 확정하려면 전체 B078 자료가 필요하다.",
        "",
        "괴리는 연관성과 예측오차를 뜻하며 인과효과가 아니다. ‘통과형’이라는 명칭도 환승 때문에 매출이 낮다고 확정하는 표현이 아니라 후속 검증 가설이다.",
    ]
    (out / "EDA_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sales", default="data/raw/seoul_commercial_sales_dong_2025.csv")
    parser.add_argument("--stores", default="data/raw/seoul_commercial_stores_dong_2025.csv")
    parser.add_argument("--flow", default="data/raw/seoul_commercial_floating_population_dong.csv")
    parser.add_argument("--candidates", default="data/processed/local_transit_30min/time_period_candidates.csv")
    parser.add_argument("--output", default="data/processed/flow_sales_gap")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
