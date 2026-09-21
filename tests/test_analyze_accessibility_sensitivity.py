import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import analyze_accessibility_sensitivity as mod  # noqa: E402


def _candidates() -> pd.DataFrame:
    # A: 세 시간대 모두 0.9 / B: 한 시간대만 0.4 / C: 모두 0.6 / D: 모두 0.3
    return pd.DataFrame({
        "area_code": ["A", "B", "C", "D"],
        "area_name": ["a", "b", "c", "d"],
        "ratio_08": [0.9, 0.9, 0.6, 0.3],
        "ratio_14": [0.9, 0.4, 0.6, 0.3],
        "ratio_19": [0.9, 0.9, 0.6, 0.3],
        "minimum_period_ratio": [0.9, 0.4, 0.6, 0.3],
        "access_tier": ["core", "exploration", "base", "exploration"],
    })


def test_filter_requires_all_three_periods():
    got = mod.filter_candidates(_candidates(), 0.5)
    assert set(got["area_code"]) == {"A", "C"}  # B는 한 시간대가 0.4라 제외


def test_thresholds_are_nested():
    c = _candidates()
    s25 = set(mod.filter_candidates(c, 0.25)["area_code"])
    s50 = set(mod.filter_candidates(c, 0.50)["area_code"])
    s80 = set(mod.filter_candidates(c, 0.80)["area_code"])
    assert s80 <= s50 <= s25
    assert (len(s25), len(s50), len(s80)) == (4, 2, 1)


def test_jaccard_matches_hand_calculation():
    assert mod.jaccard({"a", "b", "c"}, {"b", "c", "d"}) == 0.5
    assert mod.jaccard(set(), set()) != mod.jaccard(set(), set())  # nan


def test_top_areas_uses_purpose_and_rank():
    ranked = pd.DataFrame({
        "area_code": ["1", "2", "3", "4"],
        "purpose": ["식사", "식사", "카페", "식사"],
        "purpose_rank": [1.0, 2.0, 1.0, 3.0],
    })
    assert mod.top_areas(ranked, "식사", n=2) == {"1", "2"}
    assert mod.top_areas(ranked, "카페", n=2) == {"3"}


def test_boundary_only_contains_areas_dropped_by_50_or_80():
    c = mod.filter_candidates(_candidates(), 0.25)
    top25 = {"식사": {"C"}, "공부": {"D"}}
    b = mod.boundary_candidates(c, top25).set_index("area_code")
    assert set(b.index) == {"B", "C", "D"}  # A는 80%까지 유지 -> 경계 아님
    assert b.loc["C", "first_dropped_at"] == "80pct"  # 50%는 통과, 80%에서 탈락
    assert b.loc["B", "first_dropped_at"] == "50pct"
    assert b.loc["C", "top10_purposes_at_25pct"] == "식사"
    assert bool(b.loc["D", "study_top10_at_25pct"]) is True
