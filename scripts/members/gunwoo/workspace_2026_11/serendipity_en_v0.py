#!/usr/bin/env python3
"""의외성 랭킹(SERP-v0)의 회귀 두 개만 Elastic Net으로 바꾼 EN판.

바꾼 것 (나머지 R·U 가중치, R 하한, MMR, 관성 기준선은 SERP-v0 그대로)
  1) 회귀: numpy Ridge(α=1) → StandardScaler + ElasticNetCV(α·l1_ratio 교차검증). 바깥 5겹은 SERP-v0와 같음
  2) 설명변수: 구조 변수 + 시간대 도달률(08·14·19시) + 공공 태그(노포·10년+·오래된카페·착한가격)
  3) 유입 타깃: log(비일상 유입 × 도달률) → log(비일상 유입) (누수 수정, elastic_net_v0.py 참고)

실행: ~/.venvs/maximus/bin/python 분석/serendipity_en_v0.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)

HERE = Path(__file__).resolve().parents[1]
REPO = HERE / "maximus-analysis-archive"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_serendipity_ranking as serp  # noqa: E402
from elastic_net_v0 import L1_GRID, extra_features  # noqa: E402

OUT = HERE / "데이터/가공/elastic_net"


def en_oof(X: np.ndarray, y: np.ndarray, folds: np.ndarray, alpha: float) -> np.ndarray:
    """ridge_oof와 같은 바깥 폴드, 안에서 ElasticNetCV. alpha 인자는 무시(교차검증으로 정함)."""
    pred = np.zeros_like(y, dtype=float)
    for f in np.unique(folds):
        tr, te = folds != f, folds == f
        m = make_pipeline(StandardScaler(), ElasticNetCV(l1_ratio=L1_GRID, alphas=60, max_iter=20000,
                                                         cv=KFold(5, shuffle=True, random_state=0)))
        pred[te] = m.fit(X[tr], y[tr]).predict(X[te])
    return pred


def main() -> None:
    # --v1: 여가 v1 규칙(주점→여가, 관광특구 추천 제외). --serp: EN 바꿈 없이 원래 SERP-v0(Ridge·원래 타깃)
    root, suffix = REPO, ""
    if "--v1" in sys.argv:
        from leisure_v1_align import block_tourism_zones, build_v1_root
        root, suffix = build_v1_root(), "_v1"
        block_tourism_zones(serp)
    area, purpose = serp.load_inputs(root, 20254, use_movement=True)
    if "--serp" in sys.argv:
        full, _ = serp.build_serendipity(area, purpose, serp.Config())
        full = full.sort_values(["purpose", "mmr_rank", "score_rank"], na_position="last")
        full[serp.OUT_COLS].to_csv(OUT / f"serendipity_ranking_serp{suffix}.csv", index=False, encoding="utf-8-sig")
        print("wrote", f"serendipity_ranking_serp{suffix}.csv", len(full))
        return
    extra = extra_features(area.reset_index(drop=True))
    extra.index = area["area_code"].to_numpy()
    base_matrix = serp.structural_matrix

    def structural_plus(df: pd.DataFrame) -> np.ndarray:
        return np.c_[base_matrix(df), extra.loc[df["area_code"].to_numpy()].to_numpy(float)]

    serp.ridge_oof = en_oof
    serp.structural_matrix = structural_plus
    if "--ddm" in sys.argv:
        # 동대문구발 실제 유입(서울 생활이동 2026-07, 도착=기타 장소). 관성 기준선 '과거 유입순'도 이 값으로 바꾼다.
        ddm = pd.read_csv(OUT / "dongdaemun_od_inflow_202607.csv", dtype={"area_code": str})
        area = area.merge(ddm[["area_code", "ddm_nonroutine"]], on="area_code", how="left")
        area["observed_inflow"] = area["ddm_nonroutine"].fillna(0)
        area["log_observed"] = np.log1p(area["observed_inflow"])
        out_name = "serendipity_ranking_en_ddm.csv"
    else:
        area["log_observed"] = np.log1p(area["inflow_nonroutine"].fillna(0))  # 누수 수정. observed_inflow(관성 기준선)는 그대로
        out_name = "serendipity_ranking_en.csv"
    out_name = out_name.replace(".csv", f"{suffix}.csv")

    full, _ = serp.build_serendipity(area, purpose, serp.Config())
    full = full.sort_values(["purpose", "mmr_rank", "score_rank"], na_position="last")
    full[serp.OUT_COLS].to_csv(OUT / out_name, index=False, encoding="utf-8-sig")
    print("wrote", out_name, len(full))


if __name__ == "__main__":
    main()
