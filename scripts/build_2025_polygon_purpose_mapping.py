#!/usr/bin/env python3
"""Publish the year-matched purpose feature mart for official-area polygons."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


SOURCE_DATASET = "서울시 상권분석서비스(점포-상권)"
PURPOSE_SCOPE = {
    "식사": "음식점·제과·주점 업종",
    "카페": "커피-음료 업종",
    "공부": "독서실·서적·문구·학원 업종",
    "쇼핑": "의류·화장품·식품소매·생활소매 업종",
    "여가문화": "오락·스포츠·숙박 업종",
}


def build_2025_polygon_mapping(features: pd.DataFrame) -> pd.DataFrame:
    """Keep only 2025 records and make the polygon-code join provenance explicit."""
    required = {
        "quarter", "area_code", "area_name", "area_type_name", "purpose",
        "purpose_store_count", "purpose_sales_amount", "purpose_time_fit_amount",
        "purpose_supply_score", "path_v0_score",
    }
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError(f"필수 열 누락: {missing}")

    out = features.loc[(features["quarter"].astype(int) // 10) == 2025].copy()
    out["area_code"] = out["area_code"].astype(str)
    out["source_year"] = 2025
    out["source_dataset"] = SOURCE_DATASET
    out["mapping_method"] = "상권코드 직접 결합"
    out["purpose_industry_scope"] = out["purpose"].map(PURPOSE_SCOPE)
    out["historical_2025_use_allowed"] = True
    return out.sort_values(["quarter", "purpose", "area_code"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features",
        default="data/processed/commercial_area_purpose_features/official_area_purpose_quarter_features.csv",
    )
    parser.add_argument("--output-dir", default="data/processed/polygon_purpose_mapping_2025")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(args.features, dtype={"area_code": str})
    mapped = build_2025_polygon_mapping(source)
    mapped.to_csv(output_dir / "official_area_purpose_polygon_mapping_2025.csv", index=False, encoding="utf-8-sig")
    latest = mapped.loc[mapped["quarter"] == mapped["quarter"].max()].copy()
    latest.to_csv(output_dir / "official_area_purpose_polygon_mapping_2025q4.csv", index=False, encoding="utf-8-sig")

    report = f"""# 2025 목적별 공식 상권 폴리곤 매핑\n\n- 원천: {SOURCE_DATASET}_2025년\n- 매핑: 서울시 공식 상권 코드와 분석 후보 폴리곤의 `area_code` 직접 결합\n- 범위: 2025년 4개 분기 × 접근성 후보 공식 상권 {mapped.area_code.nunique():,}개 × 5개 목적\n- 목적별 업종: 식사(음식점·제과·주점), 카페(커피-음료), 공부(독서실·서적·문구·학원), 쇼핑(의류·화장품·식품소매·생활소매), 여가문화(오락·스포츠·숙박)\n\n이 파일은 2025년 기준 점포 수, 목적 업종 비중, 목적 적합 시간대 매출 및 PATH-v0 점수를 유지한다. 2026-09-16 문화 POI 스냅샷은 시점 불일치로 이 파일에 결합하지 않았다.\n"""
    (output_dir / "README.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
