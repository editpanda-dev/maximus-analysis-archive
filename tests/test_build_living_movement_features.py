import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_living_movement_features.py"
SPEC = importlib.util.spec_from_file_location("living_movement", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_time_slot_boundaries():
    assert MODULE.time_slot("0600") == "morning"
    assert MODULE.time_slot("0940") == "morning"
    assert MODULE.time_slot("1000") == "daytime"
    assert MODULE.time_slot("10") == "daytime"
    assert MODULE.time_slot("1700") == "evening"
    assert MODULE.time_slot("2200") == "night"


def test_build_features_allocates_and_normalizes_purpose_shares():
    movement = pd.DataFrame(
        {
            "admin_code": ["11110000", "11110000"],
            "time_slot": ["morning", "morning"],
            "purpose": ["commute", "shopping"],
            "etl_ymd": ["20260801", "20260801"],
            "total_cnt": [100.0, 50.0],
        }
    )
    overlap = pd.DataFrame(
        {
            "area_code": ["A", "B"],
            "admin_code": ["11110000", "11110000"],
            "overlap_share": [0.6, 0.4],
        }
    )
    features, audit = MODULE.build_features(movement, overlap, {"A", "B"})
    area_a = features.loc[features["area_code"].eq("A")].set_index("purpose")
    assert area_a.loc["commute", "inflow_count"] == 60.0
    assert area_a.loc["shopping", "inflow_count"] == 30.0
    assert area_a["purpose_share"].sum() == 1.0
    assert audit.loc[0, "area_count"] == 2
