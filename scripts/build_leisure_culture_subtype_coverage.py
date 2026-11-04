#!/usr/bin/env python3
"""Create a reproducible leisure-culture subtype coverage audit for 786 areas.

This script intentionally does not alter the 2025 PATH-v0 ranking.  It uses
the 2026 POI snapshot only to describe which current leisure-culture facility
signals are observable around each official commercial-area polygon.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


SUBTYPE_MAP = {
    "viewing_exhibition": {
        "subtype_name": "관람·전시",
        "fields": [
            "poi_museum_buffer400_count",
            "poi_art_gallery_buffer400_count",
            "poi_cinema_buffer400_count",
            "poi_exhibition_space_buffer400_count",
        ],
    },
    "performance_culture": {
        "subtype_name": "공연·문화활동",
        "fields": [
            "poi_performance_hall_buffer400_count",
            "poi_cultural_center_buffer400_count",
        ],
    },
    "outdoor_park": {
        "subtype_name": "야외·공원",
        "fields": ["poi_park_buffer400_count"],
    },
    "sports_activity": {
        "subtype_name": "스포츠·활동",
        "fields": ["poi_sports_facility_buffer400_count"],
    },
}

REQUIRED_BASE_COLUMNS = [
    "area_code",
    "area_name",
    "feature_snapshot_date",
    "historical_2025_use_allowed",
]


def _required_columns() -> list[str]:
    return REQUIRED_BASE_COLUMNS + [
        field for definition in SUBTYPE_MAP.values() for field in definition["fields"]
    ]


def build_subtype_coverage(poi: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return an area-level subtype matrix and a reproducibility audit summary."""
    if "area_code" in poi.columns and poi["area_code"].astype(str).duplicated().any():
        raise ValueError("duplicate area_code in POI features")
    missing = sorted(set(_required_columns()) - set(poi.columns))
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")

    frame = poi.copy()
    frame["area_code"] = frame["area_code"].astype(str)

    area_columns = REQUIRED_BASE_COLUMNS + [
        column
        for column in ["area_type_name", "access_tier", "coverage_status", "operation_status"]
        if column in frame.columns
    ]
    area = frame[area_columns].copy()
    area["historical_2025_use_allowed"] = area["historical_2025_use_allowed"].astype(bool)

    summary_rows: list[dict[str, object]] = []
    subtype_columns: list[str] = []
    for subtype_code, definition in SUBTYPE_MAP.items():
        count_column = f"{subtype_code}_buffer400_count"
        count = frame[definition["fields"]].fillna(0).sum(axis=1)
        area[count_column] = count.astype(int)
        area[f"has_{subtype_code}_buffer400"] = count.gt(0)
        subtype_columns.append(count_column)
        summary_rows.append(
            {
                "subtype_code": subtype_code,
                "subtype_name": definition["subtype_name"],
                "source_feature_columns": " | ".join(definition["fields"]),
                "source_feature_type_count": len(definition["fields"]),
                "covered_area_count": int(count.gt(0).sum()),
                "covered_area_share": float(count.gt(0).mean()),
                "total_buffer400_count": int(count.sum()),
                "snapshot_date": str(area["feature_snapshot_date"].iloc[0]),
                "historical_2025_use_allowed": bool(area["historical_2025_use_allowed"].all()),
            }
        )

    area["leisure_subtype_total_buffer400_count"] = area[subtype_columns].sum(axis=1)
    area["leisure_subtype_diversity"] = area[subtype_columns].gt(0).sum(axis=1)
    summary = pd.DataFrame(summary_rows)
    return area, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--poi",
        default="data/external/official_area_poi_features_20260916.csv",
        help="Current-snapshot, area-level leisure POI feature file.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/leisure_culture_subtype_coverage",
    )
    args = parser.parse_args()

    poi = pd.read_csv(args.poi, dtype={"area_code": str})
    area, summary = build_subtype_coverage(poi)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    area.to_csv(
        output_dir / "official_area_leisure_culture_subtype_coverage_786.csv",
        index=False,
        encoding="utf-8-sig",
    )
    summary.to_csv(
        output_dir / "leisure_culture_subtype_coverage_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


if __name__ == "__main__":
    main()
