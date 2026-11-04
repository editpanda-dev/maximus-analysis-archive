import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_week2_crosswork_insights.py"
SPEC = importlib.util.spec_from_file_location("week2_insights", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_build_integrated_features_labels_accessible_study_demand_signal(tmp_path):
    access = pd.DataFrame(
        [
            {"area_code": "A", "area_name": "가", "primary_district_name": "동대문구", "minimum_period_ratio": 1.0, "access_tier": "core_80pct_all_periods"},
            {"area_code": "B", "area_name": "나", "primary_district_name": "중구", "minimum_period_ratio": 0.3, "access_tier": "exploration_25pct_all_periods"},
            {"area_code": "C", "area_name": "다", "primary_district_name": "성북구", "minimum_period_ratio": 0.9, "access_tier": "core_80pct_all_periods"},
            {"area_code": "D", "area_name": "라", "primary_district_name": "광진구", "minimum_period_ratio": 0.8, "access_tier": "core_80pct_all_periods"},
        ]
    )
    study = pd.DataFrame(
        [
            {"area_code": "A", "study_stay_current_score": 90, "study_stay_current_rank": 1, "study_public_inside_count": 3, "study_public_nearby_only_count": 1, "study_cafe_inside_count": 2},
            {"area_code": "B", "study_stay_current_score": 80, "study_stay_current_rank": 2, "study_public_inside_count": 1, "study_public_nearby_only_count": 0, "study_cafe_inside_count": 1},
            {"area_code": "C", "study_stay_current_score": 30, "study_stay_current_rank": 3, "study_public_inside_count": 0, "study_public_nearby_only_count": 0, "study_cafe_inside_count": 0},
            {"area_code": "D", "study_stay_current_score": 20, "study_stay_current_rank": 4, "study_public_inside_count": 0, "study_public_nearby_only_count": 0, "study_cafe_inside_count": 0},
        ]
    )
    movement = pd.DataFrame(
        [
            {"area_code": area, "purpose": purpose, "inflow_count": count, "source_period": "20260801-20260831"}
            for area, values in {
                "A": {"school": 90, "commute": 5, "return_home": 5},
                "B": {"school": 0, "commute": 80, "return_home": 20},
                "C": {"school": 90, "commute": 5, "return_home": 5},
                "D": {"school": 10, "commute": 80, "return_home": 10},
            }.items()
            for purpose, count in values.items()
        ]
    )
    access_path, study_path, movement_path = (tmp_path / "access.csv", tmp_path / "study.csv", tmp_path / "movement.csv")
    access.to_csv(access_path, index=False)
    study.to_csv(study_path, index=False)
    movement.to_csv(movement_path, index=False)

    result, summary = MODULE.build_integrated_features(access_path, study_path, movement_path)

    assert len(result) == 4
    assert result.loc[result.area_code.eq("A"), "integration_segment"].item() == "study_ready_signal"
    assert result.loc[result.area_code.eq("C"), "integration_segment"].item() == "demand_signal_feature_gap"
    assert summary["area_count"] == 4
    assert summary["living_movement_period_count"] == 1
