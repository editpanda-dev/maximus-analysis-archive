#!/usr/bin/env python3
"""여가문화 v1(지우진, codex/jiujin/leisure-culture-subtypes) 규칙 두 가지를 SERP·EN 입력에 맞춘다.

  1) 주점 재분류: 호프-간이주점·일반주점을 식사에서 빼고 여가문화로 옮긴다.
     → 저장소 build_commercial_area_purpose_features.build_features를 그대로 다시 돌려
       목적별 점포·매출·PATH-v0 점수를 새로 만든다(원천: data/raw/commercial_area/*.zip).
  2) 관광특구 6곳: 분석 대상(회귀·관성 기준선)에는 남기고 추천만 막는다(v1의 recommendation_eligible=False).

v1의 문화 POI·카카오 야간 POI·크기 보정은 2026 스냅샷이라 여기선 넣지 않는다.
결과는 저장소를 건드리지 않고 데이터/가공/elastic_net/v1root/ 아래 가짜 루트로 만든다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
REPO = HERE / "maximus-analysis-archive"
V1ROOT = HERE / "데이터/가공/elastic_net/v1root"
LIQUOR = {"호프-간이주점", "일반주점"}
TOURISM_TYPE = "관광특구"
FEATURE_FILE = "commercial_area_purpose_features/official_area_purpose_quarter_features.csv"


def build_v1_root() -> Path:
    """주점을 여가로 옮긴 목적 피처 + 나머지 data/processed 폴더 링크."""
    sys.path.insert(0, str(REPO))
    from scripts import build_purpose_features as bpf
    from scripts.build_commercial_area_accessibility import read_zip_csv
    from scripts.build_commercial_area_purpose_features import build_features

    bpf.PURPOSE_INDUSTRIES["식사"] -= LIQUOR
    bpf.PURPOSE_INDUSTRIES["여가문화"] |= LIQUOR
    raw = REPO / "data/raw/commercial_area"
    feats = build_features(read_zip_csv(raw / "commercial_store_2025.zip"), read_zip_csv(raw / "commercial_sales_2025.zip"),
                           pd.read_csv(REPO / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv",
                                       dtype={"area_code": str}))
    proc = V1ROOT / "data/processed"
    (proc / FEATURE_FILE).parent.mkdir(parents=True, exist_ok=True)
    feats.to_csv(proc / FEATURE_FILE, index=False, encoding="utf-8-sig")
    for d in ["commercial_area_sales_gap", "commercial_area_accessibility", "week2_integration"]:
        link = proc / d
        if not link.exists():
            link.symlink_to(REPO / "data/processed" / d)
    return V1ROOT


def block_tourism_zones(serp) -> None:
    """build_serendipity 안에서 관광특구의 최종 점수를 NaN으로 만들어 추천(MMR)에서 뺀다.
    add_unexpectedness가 돌려준 목적별 표를 잡아 두고, 바로 다음 combine_scores에서 가린다."""
    orig_u, orig_c = serp.add_unexpectedness, serp.combine_scores
    cur: dict[str, pd.DataFrame] = {}

    def add_u(g, inertia, cfg):
        cur["g"] = orig_u(g, inertia, cfg)
        return cur["g"]

    def combine(r, u, floor):
        s = orig_c(r, u, floor)
        return s.where(cur["g"]["area_type_name"].ne(TOURISM_TYPE).to_numpy(), np.nan)

    serp.add_unexpectedness, serp.combine_scores = add_u, combine


if __name__ == "__main__":
    root = build_v1_root()
    f = pd.read_csv(root / "data/processed" / FEATURE_FILE, dtype={"area_code": str})
    print(f[f.quarter == f.quarter.max()].groupby("purpose")["purpose_store_count"].sum())
