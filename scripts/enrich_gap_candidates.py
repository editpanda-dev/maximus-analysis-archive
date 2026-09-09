#!/usr/bin/env python3
"""Test whether resident, workplace and attracting-facility context explains gap candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def normalize_code(value) -> str:
    digits = "".join(x for x in str(value).split(".")[0] if x.isdigit())
    return digits[:8].zfill(8)


def dominant_context_driver(row: pd.Series, columns: list[str]) -> str:
    valid = {c: abs(float(row[c]) - 0.5) for c in columns if pd.notna(row[c])}
    return max(valid, key=valid.get).removesuffix("_pct") if valid else "none"


CONTEXT_LABELS = {
    "resident_population": "상주인구", "workplace_population": "직장인구",
    "workplace_resident_ratio": "직장/상주 비율", "facility_count": "집객시설", "transit_facilities": "교통시설",
    "medical_facilities": "의료시설", "university_count": "대학교",
    "department_store_count": "백화점", "theater_count": "극장", "accommodation_count": "숙박시설",
}


def read_source(path: str, rename: dict[str, str]) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="cp949", low_memory=False).rename(columns=rename)
    frame["admin_code"] = frame["행정동_코드"].map(normalize_code)
    frame = frame.rename(columns={"기준_년분기_코드": "quarter"})
    return frame


def oof_predict(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    pred = pd.Series(index=frame.index, dtype=float)
    for quarter in sorted(frame.quarter.unique()):
        train, test = frame.quarter != quarter, frame.quarter == quarter
        model = HistGradientBoostingRegressor(max_iter=300, learning_rate=.04, max_leaf_nodes=15,
                                              min_samples_leaf=20, l2_regularization=1.5,
                                              random_state=42)
        model.fit(frame.loc[train, features], frame.loc[train, "log_sales"])
        pred.loc[test] = model.predict(frame.loc[test, features])
    return pred.to_numpy()


def metrics(actual, pred, name):
    return {"model": name, "rmse_log_sales": mean_squared_error(actual, pred) ** .5,
            "mae_log_sales": mean_absolute_error(actual, pred), "r2_log_sales": r2_score(actual, pred)}


def run(args) -> None:
    base = pd.read_csv(args.base, dtype={"admin_code": str})
    flagged = pd.read_csv(args.flagged, dtype={"admin_code": str})
    flagged = flagged[flagged.gap_type != "일반형"].copy()

    resident = read_source(args.resident, {"총_상주인구_수": "resident_population"})
    workplace = read_source(args.workplace, {"총_직장_인구_수": "workplace_population"})
    facilities = read_source(args.facilities, {
        "집객시설_수": "facility_count", "종합병원_수": "general_hospital_count",
        "일반_병원_수": "hospital_count", "약국_수": "pharmacy_count", "대학교_수": "university_count",
        "백화점_수": "department_store_count", "슈퍼마켓_수": "supermarket_count", "극장_수": "theater_count",
        "숙박_시설_수": "accommodation_count", "철도_역_수": "rail_station_count",
        "지하철_역_수": "subway_station_count", "버스_정거장_수": "bus_stop_count",
    })
    rcols = ["quarter", "admin_code", "resident_population"]
    wcols = ["quarter", "admin_code", "workplace_population"]
    fcols = ["quarter", "admin_code", "facility_count", "general_hospital_count", "hospital_count",
             "pharmacy_count", "university_count", "department_store_count", "supermarket_count", "theater_count",
             "accommodation_count", "rail_station_count", "subway_station_count", "bus_stop_count"]
    frame = base.merge(resident[rcols], on=["quarter", "admin_code"], how="left")
    frame = frame.merge(workplace[wcols], on=["quarter", "admin_code"], how="left")
    frame = frame.merge(facilities[fcols], on=["quarter", "admin_code"], how="left")

    added = ["resident_population", "workplace_population", "facility_count", "general_hospital_count",
             "hospital_count", "pharmacy_count", "university_count", "department_store_count", "supermarket_count",
             "theater_count", "accommodation_count", "rail_station_count", "subway_station_count", "bus_stop_count"]
    for col in added:
        frame[f"log_{col}"] = np.log1p(frame[col].fillna(0))
    expanded_features = ["log_flow", "log_stores", "quarter_index"] + [f"log_{c}" for c in added]
    expanded_pred = oof_predict(frame, expanded_features)
    base_pred = frame["predicted_log_sales"].to_numpy()
    comparison = pd.DataFrame([
        metrics(frame.log_sales, base_pred, "유동+점포"),
        metrics(frame.log_sales, expanded_pred, "유동+점포+상주+직장+집객시설"),
    ])
    frame["expanded_predicted_log_sales"] = expanded_pred
    frame["expanded_gap_log"] = frame.log_sales - expanded_pred

    latest = frame.sort_values("quarter").groupby("admin_code", as_index=False).tail(1).copy()
    latest["workplace_resident_ratio"] = latest.workplace_population / latest.resident_population.replace(0, np.nan)
    latest["transit_facilities"] = latest[["rail_station_count", "subway_station_count", "bus_stop_count"]].sum(axis=1)
    latest["medical_facilities"] = latest[["general_hospital_count", "hospital_count", "pharmacy_count"]].sum(axis=1)
    context = ["resident_population", "workplace_population", "workplace_resident_ratio", "facility_count", "transit_facilities",
               "medical_facilities", "university_count", "department_store_count", "theater_count", "accommodation_count"]
    for col in context:
        latest[f"{col}_pct"] = latest[col].rank(pct=True, method="average")

    residual = frame[frame.admin_code.isin(flagged.admin_code)].groupby("admin_code").agg(
        base_mean_abs_gap=("gap_log", lambda x: x.abs().mean()),
        expanded_mean_abs_gap=("expanded_gap_log", lambda x: x.abs().mean()),
    ).reset_index()
    residual["gap_reduction_pct"] = (1 - residual.expanded_mean_abs_gap / residual.base_mean_abs_gap) * 100
    pct_cols = [f"{c}_pct" for c in context]
    result = flagged.merge(latest[["admin_code"] + context + pct_cols], on="admin_code", how="left").merge(residual, on="admin_code")
    result["dominant_context_driver"] = result.apply(lambda x: dominant_context_driver(x, pct_cols), axis=1)
    result["dominant_context_direction"] = result.apply(
        lambda x: "상위권" if x.get(f"{x.dominant_context_driver}_pct", .5) >= .5 else "하위권", axis=1)
    result["dominant_context_label"] = result.apply(
        lambda x: f"{CONTEXT_LABELS.get(x.dominant_context_driver, x.dominant_context_driver)} {x.dominant_context_direction}", axis=1)
    result["context_data_warning"] = np.where(
        result[["resident_population", "workplace_population", "facility_count"]].isna().any(axis=1),
        "맥락자료 일부 결측", "")
    result["context_explanation"] = result.apply(
        lambda x: (f"추가 맥락변수 적용 후 절대 잔차가 {x.gap_reduction_pct:.1f}% 감소했다. "
                   f"151개 후보 중 가장 두드러진 맥락은 {x.dominant_context_label}이며, "
                   "감소율이 양수이면 해당 변수가 기존 괴리의 일부를 설명한다."), axis=1)
    result = result.sort_values("gap_reduction_pct", ascending=False)

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "candidate_context_features.csv", index=False, encoding="utf-8-sig")
    result.to_csv(out / "gap_13_context_validation.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(out / "context_model_comparison.csv", index=False, encoding="utf-8-sig")

    lines = ["# 13개 괴리 후보 맥락변수 검증", "", "## 모델 비교", "",
             f"유동인구와 점포 수만 사용한 분기 홀드아웃 모형의 로그매출 R²는 {comparison.iloc[0].r2_log_sales:.3f}이다. 상주인구·직장인구·집객시설을 추가한 모형은 {comparison.iloc[1].r2_log_sales:.3f}이다. 전체 성능이 개선되면 괴리 일부가 주거·업무·시설 구조로 설명된다는 뜻이다.", "",
             "## 후보별 검증", "", "|유형|행정동|잔차 감소율|직장/상주|교통시설|의료시설|두드러진 맥락|", "|---|---|---:|---:|---:|---:|---|"]
    for _, x in result.iterrows():
        ratio = "자료없음" if pd.isna(x.workplace_resident_ratio) else f"{x.workplace_resident_ratio:.2f}"
        warning = f" ({x.context_data_warning})" if x.context_data_warning else ""
        lines.append(f"|{x.gap_type}|{x.dong_name}|{x.gap_reduction_pct:.1f}%|{ratio}|{x.transit_facilities:.0f}|{x.medical_facilities:.0f}|{x.dominant_context_label}{warning}|")
    lines += ["", "## 해석", "",
              "잔차 감소율이 크면 상주·직장인구 또는 집객시설이 기존 유동–매출 괴리의 일부를 설명한다. 감소율이 음수이면 변수를 추가해도 해당 지역의 특수성이 설명되지 않았으며, 업종별 객단가·도매 거래·행정동 내부 공간 불일치·B078 이동목적 같은 다른 원인을 우선 검토해야 한다.", "",
              "집객시설 수는 시설의 규모와 실제 이용량을 반영하지 않는다. 이 분석은 원인 확정이 아니라 다음에 붙일 POI와 B078 변수를 고르는 진단 단계다."]
    (out / "CONTEXT_VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    plt.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ordered = result.sort_values("gap_reduction_pct")
    ax.barh(ordered.dong_name, ordered.gap_reduction_pct, color=np.where(ordered.gap_reduction_pct >= 0, "#F4B400", "#9AA0A6"))
    ax.axvline(0, color="#222", lw=.8)
    ax.set(xlabel="맥락변수 추가 후 절대 잔차 감소율 (%)", ylabel="", title="상주·직장·집객시설이 괴리를 얼마나 설명했는가")
    fig.tight_layout(); fig.savefig(out / "gap_reduction_by_context.png", dpi=180); plt.close(fig)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="data/processed/flow_sales_gap/candidate_dong_features.csv")
    p.add_argument("--flagged", default="data/processed/flow_sales_gap/flow_sales_gap_candidates.csv")
    p.add_argument("--resident", default="data/raw/seoul_resident_population_dong.csv")
    p.add_argument("--workplace", default="data/raw/seoul_workplace_population_dong.csv")
    p.add_argument("--facilities", default="data/raw/seoul_attracting_facilities_dong.csv")
    p.add_argument("--output", default="data/processed/flow_sales_gap/context_validation")
    return p.parse_args()


if __name__ == "__main__": run(parse_args())
