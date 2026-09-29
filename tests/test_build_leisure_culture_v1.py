import pandas as pd
import subprocess
import sys


def _base_inputs():
    base = pd.DataFrame(
        {
            "area_code": ["1", "2", "3"],
            "area_name": ["일반 상권", "관광특구", "조용한 상권"],
            "area_type_name": ["발달상권", "관광특구", "골목상권"],
            "purpose": ["여가문화"] * 3,
            "path_v0_score": [60.0, 95.0, 40.0],
            "purpose_store_count": [10, 50, 2],
            "purpose_sales_amount": [1000.0, 5000.0, 100.0],
            "purpose_time_fit_amount": [600.0, 4000.0, 20.0],
            "minimum_period_ratio": [0.6, 0.8, 0.3],
        }
    )
    poi = pd.DataFrame(
        {
            "area_code": ["1", "2", "3"],
            "area_name": ["일반 상권", "관광특구", "조용한 상권"],
            "area_type_name": ["발달상권", "관광특구", "골목상권"],
            "feature_snapshot_date": ["2026-09-16"] * 3,
            "historical_2025_use_allowed": [False] * 3,
            "culture_inside_count": [4, 10, 0],
            "culture_buffer400_count": [7, 30, 1],
            "culture_inside_diversity": [2, 5, 0],
            "culture_buffer400_diversity": [3, 6, 1],
        }
    )
    nightlife = pd.DataFrame(
        {
            "area_code": ["1", "2", "3"],
            "nightlife_store_count": [8, 20, 0],
            "nightlife_sales_amount": [1000.0, 3000.0, 0.0],
            "nightlife_evening_sales_amount": [900.0, 2000.0, 0.0],
            "nightlife_late_sales_amount": [100.0, 500.0, 0.0],
        }
    )
    area = pd.DataFrame({"area_code": ["1", "2", "3"], "area_km2": [0.1, 2.0, 0.1], "store_count_total": [20, 300, 3]})
    return base, poi, nightlife, area


def test_build_leisure_v1_keeps_all_areas_excludes_tourism_and_separates_current_poi():
    from scripts.build_leisure_culture_v1 import build_leisure_v1

    result, audit = build_leisure_v1(*_base_inputs())

    assert len(result) == 3
    assert result["area_code"].nunique() == 3
    tourism = result.loc[result["area_code"] == "2"].iloc[0]
    assert tourism["recommendation_eligible"] == False
    assert tourism["recommendation_exclusion_reason"] == "tourism_special_zone"
    assert tourism["current_poi_historical_use_allowed"] == False
    assert result.loc[result["area_code"] == "1", "poi_nearby_only_count"].iat[0] == 3
    assert result.loc[result["area_code"] == "1", "nightlife_prime_time_share"].iat[0] == 1.0
    assert "상권 내부 문화 POI" in result.loc[result["area_code"] == "1", "recommendation_reason"].iat[0]
    assert audit["tourism_special_zone_count"] == 1
    assert "raw_score_vs_area_km2_pearson" in audit
    assert "adjusted_score_vs_total_stores_pearson" in audit


def test_build_leisure_v1_uses_evening_and_late_night_sales_only_for_nightlife_fit():
    from scripts.build_leisure_culture_v1 import build_leisure_v1

    base, poi, nightlife, area = _base_inputs()
    nightlife.loc[0, "nightlife_evening_sales_amount"] = 0.0
    nightlife.loc[0, "nightlife_late_sales_amount"] = 0.0

    result, _ = build_leisure_v1(base, poi, nightlife, area)

    first = result.loc[result["area_code"] == "1"].iloc[0]
    assert first["nightlife_prime_time_share"] == 0.0
    assert first["nightlife_time_fit_score"] < result.loc[result["area_code"] == "2", "nightlife_time_fit_score"].iat[0]


def test_build_leisure_v1_rejects_duplicate_codes_and_noncurrent_purpose_rows():
    from scripts.build_leisure_culture_v1 import build_leisure_v1

    base, poi, nightlife, area = _base_inputs()
    duplicated = pd.concat([poi, poi.iloc[[0]]], ignore_index=True)
    try:
        build_leisure_v1(base, duplicated, nightlife, area)
    except ValueError as error:
        assert "duplicate area_code" in str(error)
    else:
        raise AssertionError("duplicate POI area codes must fail")

    wrong_purpose = base.assign(purpose="식사")
    try:
        build_leisure_v1(wrong_purpose, poi, nightlife, area)
    except ValueError as error:
        assert "여가문화" in str(error)
    else:
        raise AssertionError("non-leisure base rows must fail")


def test_leisure_v1_script_can_be_invoked_directly_from_repository_root():
    result = subprocess.run(
        [sys.executable, "scripts/build_leisure_culture_v1.py", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
