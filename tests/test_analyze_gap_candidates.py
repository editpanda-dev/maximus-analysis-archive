import pandas as pd

from scripts.analyze_gap_candidates import ratio_index, summarize_persistence


def test_ratio_index_compares_sales_share_to_flow_share():
    assert ratio_index(0.30, 0.20) == 1.5
    assert pd.isna(ratio_index(0.30, 0.0))


def test_summarize_persistence_reports_stable_direction_and_variability():
    out = summarize_persistence(pd.Series([1.0, 1.2, 1.1, 1.3]))
    assert out["gap_same_sign_quarters"] == 4
    assert out["gap_quarter_cv"] < 0.2
