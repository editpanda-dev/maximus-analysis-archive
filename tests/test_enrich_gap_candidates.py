import pandas as pd

from scripts.enrich_gap_candidates import dominant_context_driver, normalize_code


def test_normalize_code_handles_ten_digit_boundary_code():
    assert normalize_code(1123054500) == "11230545"
    assert normalize_code(11230545) == "11230545"


def test_dominant_context_driver_uses_largest_absolute_percentile_distance():
    row = pd.Series({"workplace_pct": 0.95, "resident_pct": 0.52, "transit_pct": 0.20})
    assert dominant_context_driver(row, ["workplace_pct", "resident_pct", "transit_pct"]) == "workplace"
