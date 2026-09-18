#!/usr/bin/env python3
"""Build a current-snapshot leisure POI enrichment without rewriting PATH-v0."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


LEISURE = "여가문화"
VENUE_COLUMNS = [
    "poi_cinema_buffer400_count",
    "poi_performance_hall_buffer400_count",
    "poi_exhibition_space_buffer400_count",
    "poi_park_buffer400_count",
    "poi_sports_facility_buffer400_count",
]


def _percentile(values: pd.Series) -> pd.Series:
    return values.rank(pct=True, method="average") * 100


def build_leisure_enrichment(rankings: pd.DataFrame, poi: pd.DataFrame) -> pd.DataFrame:
    """Combine 2025 PATH-v0 leisure rows with a separate 2026 POI snapshot score."""
    base = rankings.loc[rankings["purpose"] == LEISURE].copy()
    base["area_code"] = base["area_code"].astype(str)
    features = poi.loc[poi["purpose"] == LEISURE].copy()
    features["area_code"] = features["area_code"].astype(str)

    features["activity_venue_buffer400_count"] = features[VENUE_COLUMNS].sum(axis=1)
    features["culture_core_percentile"] = _percentile(features["culture_core_buffer400_count"])
    features["culture_diversity_percentile"] = _percentile(features["culture_buffer400_diversity"])
    features["activity_venue_percentile"] = _percentile(features["activity_venue_buffer400_count"])
    features["leisure_poi_score"] = (
        0.45 * features["culture_core_percentile"]
        + 0.30 * features["culture_diversity_percentile"]
        + 0.25 * features["activity_venue_percentile"]
    )

    columns = [
        "area_code", "feature_snapshot_date", "is_static_auxiliary",
        "historical_2025_use_allowed", "coverage_status", "operation_status",
        "culture_inside_count", "culture_buffer400_count", "culture_buffer400_diversity",
        "culture_core_buffer400_count", "activity_venue_buffer400_count", "leisure_poi_score",
    ]
    out = base.merge(features[columns], on="area_code", how="inner", validate="one_to_one")
    out["historical_2025_use_allowed"] = out["historical_2025_use_allowed"].astype(bool)
    out["path_v0_percentile"] = _percentile(out["path_v0_score"])
    out["poi_enriched_score"] = 0.85 * out["path_v0_percentile"] + 0.15 * out["leisure_poi_score"]
    out = out.sort_values(["poi_enriched_score", "area_code"], ascending=[False, True]).reset_index(drop=True)
    out["leisure_poi_rank"] = np.arange(1, len(out) + 1)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rankings",
        default="data/processed/commercial_area_purpose_features/official_area_purpose_latest_rankings.csv",
    )
    parser.add_argument(
        "--poi", default="data/external/official_area_poi_features_20260916.csv"
    )
    parser.add_argument("--output-dir", default="data/processed/leisure_poi_enrichment")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rankings = pd.read_csv(args.rankings, dtype={"area_code": str})
    poi = pd.read_csv(args.poi, dtype={"area_code": str})
    enriched = build_leisure_enrichment(rankings, poi)
    enriched.to_csv(out_dir / "official_area_leisure_poi_enriched_current.csv", index=False, encoding="utf-8-sig")

    report = f"""# 여가문화 POI 보조지수\n\n- 대상: 25% 접근성 후보 공식 상권 {len(enriched):,}개\n- 기준 순위: 2025년 4분기 여가문화 PATH-v0\n- POI 기준일: {enriched['feature_snapshot_date'].iloc[0]}\n- 점수: PATH-v0 백분위 85% + 여가 POI 보조지수 15%\n- POI 보조지수: 상권·400m 문화시설 핵심 수 45% + 문화시설 다양성 30% + 영화관·공연장·전시공간·공원·스포츠시설 수 25%\n\n## 사용 제한\n\nPOI 파일은 2026년 현재 스냅샷이며 `historical_2025_use_allowed=false`다. 따라서 이 산출물은 2025년 성능검증이나 과거 매출 예측에 사용하지 않는다. 최신 여가문화 후보를 설명하는 보조 순위로만 사용하며, PATH-v0 원본 순위는 변경하지 않는다. 운영 여부 관련 필드는 원천에서 비어 있어 점수에 사용하지 않았다.\n"""
    (out_dir / "README.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
