#!/usr/bin/env python3
"""Publish a transparent, purpose-aware ranking baseline (PATH-v0).

PATH means Purpose-Aware Transit-constrained Heuristic.  It is intentionally
not presented as a learned destination-choice model: it ranks the already
reachable set using only the leakage-safe feature score built in the prior
step.  Its role is to provide a reproducible benchmark for B078-based models.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def build_rankings(features: pd.DataFrame) -> pd.DataFrame:
    """Rank candidate dongs independently inside each purpose and quarter."""
    required = {
        "quarter", "purpose", "admin_code", "dong_name", "sggnm",
        "purpose_model_input_score", "purpose_supply_score", "lagged_sales_signal",
        "minimum_period_ratio", "mean_period_ratio",
    }
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    out = features.dropna(subset=["purpose_model_input_score", "lagged_sales_signal"]).copy()
    # PATH-v0 deliberately uses no new arbitrary weighted composite: the score
    # is the predeclared supply 70% + previous-quarter consumption 30% feature.
    out["path_v0_score"] = out["purpose_model_input_score"]
    out["purpose_rank"] = out.groupby(["quarter", "purpose"])["path_v0_score"].rank(method="first", ascending=False).astype(int)
    out["accessibility_confidence"] = np.select(
        [out["minimum_period_ratio"] >= .8, out["minimum_period_ratio"] >= .5],
        ["높음", "보통"], default="낮음",
    )
    cols = [
        "quarter", "purpose", "purpose_rank", "admin_code", "dong_name", "sggnm",
        "path_v0_score", "purpose_model_input_score", "purpose_supply_score", "lagged_sales_signal",
        "minimum_period_ratio", "mean_period_ratio", "accessibility_confidence",
    ]
    return out[cols].sort_values(["quarter", "purpose", "purpose_rank", "admin_code"]).reset_index(drop=True)


def reason_text(row: pd.Series) -> str:
    supply = float(row["purpose_supply_score"])
    demand = float(row["lagged_sales_signal"])
    if supply >= 80 and demand >= 80:
        return "목적 관련 상권 구성과 직전 분기 소비 신호가 모두 강함"
    if supply >= 80:
        return "목적 관련 점포·시설 구성이 강함"
    if demand >= 80:
        return "직전 분기 목적 관련 소비 신호가 강함"
    return "후보군 평균보다 높은 목적 적합도"


def run(args: argparse.Namespace) -> None:
    root = Path(args.root)
    features = pd.read_csv(root / args.features, dtype={"admin_code": str})
    rankings = build_rankings(features)
    rankings["recommendation_reason"] = rankings.apply(reason_text, axis=1)
    latest_quarter = int(rankings["quarter"].max())
    latest = rankings[rankings["quarter"] == latest_quarter].copy()
    out = root / args.output
    out.mkdir(parents=True, exist_ok=True)
    rankings.to_csv(out / "path_v0_purpose_rankings_all_quarters.csv", index=False, encoding="utf-8-sig")
    latest.to_csv(out / "path_v0_purpose_rankings_latest.csv", index=False, encoding="utf-8-sig")
    latest.groupby("purpose", group_keys=False).head(10).to_csv(out / "path_v0_top10_by_purpose.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# PATH-v0 목적별 후보지 순위 베이스라인", "",
        "## 정의", "",
        "PATH는 **Purpose-Aware Transit-constrained Heuristic**의 약자다. 동대문구 전역 정류장·역에서 세 시간대 모두 30분 내 도달 가능한 행정동만 후보로 제한하고, 목적별 특징 변수로 각 목적 안에서 순위를 매긴 규칙기반 기준선이다.", "",
        "## 점수", "",
        "`PATH-v0 점수 = purpose_model_input_score`", "",
        "이 점수는 이미 정해 둔 `목적 공급 신호 70% + 직전 분기 소비 신호 30%`다. 공급 신호는 목적별 점포 수·점포 비중·관련 시설의 분기 내 백분위이고, 소비 신호는 직전 분기의 매출 규모·목적 매출 비중·목적 적합 시간대 매출 비중이다. 같은 분기 매출을 쓰지 않아 미래 정보 누수를 피했다.", "",
        "## 이 기준선이 할 수 있는 일과 없는 일", "",
        "- 할 수 있는 일: 공통 접근성 후보군 안에서 목적에 따라 서로 다른 1차 순위를 제시하고, 이후 학습모형과 비교할 기준을 제공한다.",
        "- 아직 할 수 없는 일: 개별 사용자의 실제 출발 정류장, 실시간 이동시간, 개인 취향을 반영하거나 실제 목적 이동량을 예측하지는 않는다. 해당 기능은 B078 전체 원본의 목적별 OD 이동량을 확보한 뒤 조건부 로짓·LightGBM/CatBoost 순위모형으로 검증한다.", "",
        "## 검증 계획", "",
        "B078 이용 가능 후에는 동일한 출발지·시간대·연령·목적 조건에서 (1) 이동시간 최단순, (2) 전체 인기순, (3) PATH-v0, (4) 학습 순위모형을 비교한다. Recall@5, NDCG@5, MRR과 strata 단위 paired bootstrap 95% CI로 평가한다.", "",
        f"## 현재 산출 범위", "",
        f"2023년 2분기부터 {latest_quarter // 10}년 {latest_quarter % 10}분기까지 순위를 계산했다. 첫 분기는 직전 분기 소비 신호가 없어 제외됐다. 최신 분기에는 목적당 {latest.groupby('purpose').size().min()}개 후보가 있다.",
    ]
    (out / "PATH_V0_BASELINE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(rankings):,} PATH-v0 ranking rows; latest quarter={latest_quarter}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--features", default="data/processed/purpose_features/purpose_dong_quarter_features.csv")
    parser.add_argument("--output", default="data/processed/purpose_rankings")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
