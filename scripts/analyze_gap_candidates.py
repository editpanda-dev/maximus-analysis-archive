#!/usr/bin/env python3
"""Explain persistent flow-sales gap candidates with demographic and purpose profiles."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.flow_sales_gap import normalize_admin_code, purpose_group


AGE_KEYS = {
    "10대": ("연령대_10_매출_금액", "연령대_10_유동인구_수"),
    "20대": ("연령대_20_매출_금액", "연령대_20_유동인구_수"),
    "30대": ("연령대_30_매출_금액", "연령대_30_유동인구_수"),
    "40대": ("연령대_40_매출_금액", "연령대_40_유동인구_수"),
    "50대": ("연령대_50_매출_금액", "연령대_50_유동인구_수"),
    "60대이상": ("연령대_60_이상_매출_금액", "연령대_60_이상_유동인구_수"),
}
TIME_KEYS = {
    "00~06": ("시간대_00~06_매출_금액", "시간대_00_06_유동인구_수"),
    "06~11": ("시간대_06~11_매출_금액", "시간대_06_11_유동인구_수"),
    "11~14": ("시간대_11~14_매출_금액", "시간대_11_14_유동인구_수"),
    "14~17": ("시간대_14~17_매출_금액", "시간대_14_17_유동인구_수"),
    "17~21": ("시간대_17~21_매출_금액", "시간대_17_21_유동인구_수"),
    "21~24": ("시간대_21~24_매출_금액", "시간대_21_24_유동인구_수"),
}

LOCAL_HYPOTHESES = {
    "둔촌1동": "일반의원·의약품 매출이 상위권이라 의료 관련 목적소비 가능성이 보이지만, 유동 규모가 하위 5%라 제외 민감도를 먼저 확인해야 한다.",
    "한강로동": "컴퓨터·가전 판매가 매출을 주도한다. 일상적 유동보다 객단가가 큰 내구재 구매가 괴리를 키웠을 가능성이 있다.",
    "제기동": "청과·반찬·미곡 판매가 상위 업종이고 60대 이상 소비집중이 높다. 전통시장형 식료품 구매 목적이 유력한 설명 가설이다.",
    "종로5·6가동": "의약품 매출과 60대 이상 소비집중이 동시에 높다. 의료·약품 구매와 도심 상업 기능이 유동 규모 이상의 매출을 만들었을 가능성이 있다.",
    "종로1·2·3·4가동": "귀금속·조명용품 등 전문 소매가 강하다. 일반 방문량보다 구매 단가와 전문 목적 방문이 중요한 상권일 가능성이 있다.",
    "월계3동": "식사 업종 비중은 높지만 기대매출의 약 72%에 그친다. 주거·생활형 유동이 많고 외부 목적소비가 상대적으로 약한지 검증할 후보이다.",
    "광희동": "청과·운동용품·음식점이 혼재하지만 괴리는 음(-)이다. 도매·통과 유동 또는 행정동 내부 상권 위치 불균형을 확인해야 한다.",
    "길동": "음식·의료 중심 생활서비스형 구성인데 기대매출의 약 68%다. 상주 생활 유동이 총유동을 키우는지 확인할 필요가 있다.",
    "삼성2동": "식사·의료·편의점 중심이며 기대매출의 약 62%다. 업무·통과 유동과 상업 소비가 공간적으로 분리되는지 검증이 필요하다.",
    "논현2동": "식사·운동·의료 업종이 강하지만 총유동 대비 매출이 낮다. 고용·통과 인구를 통제하지 않은 규모효과인지 확인해야 한다.",
    "마장동": "음식·철물·슈퍼마켓이 상위권이지만 기대매출의 약 52%다. 도매 거래나 카드에 잡히지 않는 거래 구조, 통과 유동을 함께 검토해야 한다.",
    "성수2가3동": "의류·컴퓨터 판매와 음식업이 공존하지만 기대매출의 약 49%다. 넓은 행정동 안에서 유동과 매출 발생지가 다른 공간 불일치 가능성이 있다.",
    "창신3동": "매출·유동 규모가 하위 5%이고 일부 업종 영향이 커 잔차가 불안정할 수 있다. 통과형보다 소표본·집계오차를 먼저 의심해야 한다.",
}


def ratio_index(sales_share: float, flow_share: float) -> float:
    if pd.isna(flow_share) or flow_share <= 0:
        return np.nan
    return round(float(sales_share / flow_share), 6)


def summarize_persistence(gaps: pd.Series) -> dict:
    gaps = gaps.dropna().astype(float)
    if gaps.empty:
        return {"gap_same_sign_quarters": 0, "gap_quarter_cv": np.nan}
    sign = 1 if gaps.mean() >= 0 else -1
    same = int(((gaps * sign) > 0).sum())
    cv = float(gaps.std(ddof=0) / abs(gaps.mean())) if gaps.mean() else np.nan
    return {"gap_same_sign_quarters": same, "gap_quarter_cv": cv}


def profile_shares(raw: pd.DataFrame, keys: dict, prefix: str) -> pd.DataFrame:
    rows = []
    for code, group in raw.groupby("admin_code"):
        sales_values = {label: group[sales_col].sum() for label, (sales_col, _) in keys.items()}
        flow_values = {label: group[flow_col].sum() for label, (_, flow_col) in keys.items()}
        sales_total, flow_total = sum(sales_values.values()), sum(flow_values.values())
        row = {"admin_code": code}
        for label in keys:
            ss = sales_values[label] / sales_total if sales_total else np.nan
            fs = flow_values[label] / flow_total if flow_total else np.nan
            row[f"{prefix}_{label}_sales_share"] = ss
            row[f"{prefix}_{label}_flow_share"] = fs
            row[f"{prefix}_{label}_conversion_index"] = ratio_index(ss, fs)
        rows.append(row)
    return pd.DataFrame(rows)


def build_reason(row: pd.Series) -> str:
    age_cols = [c for c in row.index if c.startswith("age_") and c.endswith("conversion_index")]
    time_cols = [c for c in row.index if c.startswith("time_") and c.endswith("conversion_index")]
    top_age = max(age_cols, key=lambda c: row[c] if pd.notna(row[c]) else -np.inf)
    top_time = max(time_cols, key=lambda c: row[c] if pd.notna(row[c]) else -np.inf)
    age = top_age.split("_")[1]
    time = top_time.split("_")[1]
    dominant = row["dominant_purpose"]
    direction = "기대보다 높은" if row["gap_type"] == "목적소비형" else "기대보다 낮은"
    raw_warning = row.get("data_quality_warning", "")
    warning = f" {raw_warning}이므로 해석을 보류해야 한다." if pd.notna(raw_warning) and raw_warning else ""
    local = LOCAL_HYPOTHESES.get(row.get("dong_name", ""), "")
    return (
        f"유동인구와 점포 수를 고려한 매출이 4개 분기 평균 {row['mean_gap_ratio']:.2f}배로 {direction} 수준이다. "
        f"매출 구성은 {dominant} 비중이 가장 크고, 유동 구성 대비 소비 집중은 {age}와 {time} 시간대에서 가장 높다. "
        f"{local} 이는 데이터 기반 가설이며 이동 목적이나 인과관계를 직접 확인한 결과는 아니다.{warning}"
    )


def run(args) -> None:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    gap = pd.read_csv(args.gap, dtype={"admin_code": str})
    quarters = pd.read_csv(args.quarters, dtype={"admin_code": str})
    flagged = gap[gap["gap_type"] != "일반형"].copy()
    flagged["data_quality_warning"] = flagged["data_quality_warning"].fillna("")
    codes = set(flagged["admin_code"])

    sales = pd.read_csv(args.sales, encoding="cp949", low_memory=False)
    flow = pd.read_csv(args.flow, encoding="cp949", low_memory=False)
    for df in (sales, flow):
        df["admin_code"] = df["행정동_코드"].map(normalize_admin_code)
    sales, flow = sales[sales.admin_code.isin(codes)], flow[flow.admin_code.isin(codes)]

    # One sales row per dong-quarter after summing services; join once to flow to avoid duplication.
    sales_demo_cols = [x[0] for x in AGE_KEYS.values()] + [x[0] for x in TIME_KEYS.values()]
    sales_demo = sales.groupby(["admin_code", "기준_년분기_코드"], as_index=False)[sales_demo_cols].sum()
    flow_cols = [x[1] for x in AGE_KEYS.values()] + [x[1] for x in TIME_KEYS.values()]
    flow_demo = flow.groupby(["admin_code", "기준_년분기_코드"], as_index=False)[flow_cols].sum()
    demo = sales_demo.merge(flow_demo, on=["admin_code", "기준_년분기_코드"], how="inner")
    age = profile_shares(demo, AGE_KEYS, "age")
    time = profile_shares(demo, TIME_KEYS, "time")

    purpose = sales.copy()
    purpose["purpose"] = purpose["서비스_업종_코드_명"].map(purpose_group)
    purpose = purpose.groupby(["admin_code", "purpose"], as_index=False)["당월_매출_금액"].sum()
    purpose["share"] = purpose["당월_매출_금액"] / purpose.groupby("admin_code")["당월_매출_금액"].transform("sum")
    purpose_wide = purpose.pivot(index="admin_code", columns="purpose", values="share").fillna(0).add_prefix("purpose_share_").reset_index()
    dominant = purpose.sort_values("share", ascending=False).groupby("admin_code").head(1)[["admin_code", "purpose"]]
    dominant = dominant.rename(columns={"purpose": "dominant_purpose"})

    persistence = []
    for code, group in quarters[quarters.admin_code.isin(codes)].groupby("admin_code"):
        persistence.append({"admin_code": code, **summarize_persistence(group["gap_z"])})
    persistence = pd.DataFrame(persistence)

    detail = flagged.merge(age, on="admin_code").merge(time, on="admin_code")
    detail = detail.merge(purpose_wide, on="admin_code").merge(dominant, on="admin_code").merge(persistence, on="admin_code")
    detail["sales_per_store"] = detail["sales_amount"] / detail["store_count"].replace(0, np.nan)
    detail["flow_per_store"] = detail["floating_population"] / detail["store_count"].replace(0, np.nan)
    detail["reason_hypothesis"] = detail.apply(build_reason, axis=1)
    detail = detail.sort_values("mean_gap_z", ascending=False)
    detail.to_csv(output / "gap_13_detailed_profiles.csv", index=False, encoding="utf-8-sig")

    # Compact reader-facing table.
    compact_rows = []
    for _, row in detail.iterrows():
        age_cols = [c for c in detail if c.startswith("age_") and c.endswith("conversion_index")]
        time_cols = [c for c in detail if c.startswith("time_") and c.endswith("conversion_index")]
        top_age = max(age_cols, key=lambda c: row[c] if pd.notna(row[c]) else -np.inf).split("_")[1]
        top_time = max(time_cols, key=lambda c: row[c] if pd.notna(row[c]) else -np.inf).split("_")[1]
        compact_rows.append({
            "유형": row.gap_type, "행정동": row.dong_name, "자치구": row.sggnm,
            "실제_기대_매출비": row.mean_gap_ratio, "평균_괴리_z": row.mean_gap_z,
            "주요_목적군": row.dominant_purpose, "소비집중_연령": top_age,
            "소비집중_시간": top_time, "상위_3개_업종": row.top_3_industries,
            "데이터_주의": row.data_quality_warning, "분석_해석": row.reason_hypothesis,
        })
    compact = pd.DataFrame(compact_rows)
    compact.to_csv(output / "gap_13_summary.csv", index=False, encoding="utf-8-sig")

    lines = ["# 반복 유동–매출 괴리 13개 행정동 분석", "",
             "## 분석 기준", "",
             "2025년 네 분기 모두 같은 방향의 잔차가 나타나고, 그중 세 분기 이상에서 분기 내 절대 z값이 1 이상인 행정동을 분석했다. 매출 연령·시간대 구성과 유동인구 구성을 나누어 `매출 비중 ÷ 유동 비중`을 소비집중지수로 계산했다. 1보다 크면 해당 집단이 유동 비중에 비해 매출에 더 크게 기여했다는 뜻이다.", "",
             "## 후보별 해석", ""]
    for _, row in compact.iterrows():
        lines += [f"### {row['행정동']} ({row['유형']})", "", row["분석_해석"], ""]
    lines += ["## 추천모델 적용", "",
              "목적소비형을 그대로 정답 라벨로 사용하지 않는다. 괴리지수는 후보 발굴 변수로 넣고, 식사·카페·공부·쇼핑·여가문화 목적별 업종 비중과 시간대 적합도를 별도 특징으로 사용한다. 통과형도 제거하지 않고 비교군으로 남겨 모델이 같은 접근성과 유동 규모에서 소비가 약한 패턴을 학습하게 한다.", "",
              "둔촌1동과 창신3동은 규모 하위 5% 경고가 있어 학습 시 표본가중치를 낮추거나 최소 유동·점포 기준을 적용한다. 용두동과 신설동은 2025년과 2026년 행정동 코드 경계가 달라 이번 13개 후보 분석 이전 결합 단계에서 제외됐다.", "",
              "## 해석 한계", "",
              "유동인구와 카드 추정매출은 집계자료다. 연령별 소비집중지수는 특정 개인의 결제를 의미하지 않으며, 괴리가 환승·관광·병원·도매시장 때문에 발생했다고 확정할 수 없다. 전체 B078 이동목적 자료와 POI·환승역 자료를 결합한 뒤 가설을 재검증해야 한다."]
    (output / "GAP_13_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    plt.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    purpose_cols = [c for c in detail if c.startswith("purpose_share_")]
    chart = detail.set_index("dong_name")[purpose_cols].rename(columns=lambda c: c.replace("purpose_share_", ""))
    fig, ax = plt.subplots(figsize=(10, 6.5))
    chart.plot(kind="barh", stacked=True, ax=ax, colormap="YlOrBr")
    ax.set(xlabel="2025년 목적군별 매출 비중", ylabel="", title="13개 괴리 후보의 매출 목적 구성")
    ax.legend(title="목적군", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(output / "gap_13_purpose_mix.png", dpi=180)
    plt.close(fig)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--gap", default="data/processed/flow_sales_gap/flow_sales_gap_candidates.csv")
    p.add_argument("--quarters", default="data/processed/flow_sales_gap/candidate_dong_features.csv")
    p.add_argument("--sales", default="data/raw/seoul_commercial_sales_dong_2025.csv")
    p.add_argument("--flow", default="data/raw/seoul_commercial_floating_population_dong.csv")
    p.add_argument("--output", default="data/processed/flow_sales_gap/gap_13_analysis")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
