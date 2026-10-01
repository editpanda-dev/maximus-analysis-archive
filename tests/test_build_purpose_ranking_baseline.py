import pandas as pd

from scripts.build_purpose_ranking_baseline import build_rankings


def test_build_rankings_ranks_within_purpose_and_keeps_accessibility_evidence():
    features = pd.DataFrame({
        "quarter": [20254, 20254, 20254, 20254],
        "purpose": ["식사", "식사", "카페", "카페"],
        "admin_code": ["1", "2", "1", "2"],
        "dong_name": ["가", "나", "가", "나"],
        "sggnm": ["A", "A", "A", "A"],
        "purpose_model_input_score": [80.0, 70.0, 55.0, 90.0],
        "purpose_supply_score": [81.0, 71.0, 56.0, 91.0],
        "lagged_sales_signal": [78.0, 68.0, 54.0, 89.0],
        "minimum_period_ratio": [1.0, .5, 1.0, .5],
        "mean_period_ratio": [1.0, .7, 1.0, .7],
    })
    out = build_rankings(features)
    meal = out[out["purpose"] == "식사"].sort_values("purpose_rank")
    assert meal.iloc[0]["dong_name"] == "가"
    assert meal.iloc[0]["purpose_rank"] == 1
    assert meal.iloc[0]["accessibility_confidence"] == "높음"
    assert meal.iloc[1]["accessibility_confidence"] == "보통"
    assert out["path_v0_score"].equals(out["purpose_model_input_score"])


def test_build_rankings_excludes_rows_without_lagged_signal():
    features = pd.DataFrame({
        "quarter": [20251, 20252], "purpose": ["식사", "식사"], "admin_code": ["1", "1"],
        "dong_name": ["가", "가"], "sggnm": ["A", "A"], "purpose_model_input_score": [float("nan"), 70.0],
        "purpose_supply_score": [80.0, 80.0], "lagged_sales_signal": [float("nan"), 60.0],
        "minimum_period_ratio": [1.0, 1.0], "mean_period_ratio": [1.0, 1.0],
    })
    out = build_rankings(features)
    assert len(out) == 1
    assert out.iloc[0]["quarter"] == 20252
