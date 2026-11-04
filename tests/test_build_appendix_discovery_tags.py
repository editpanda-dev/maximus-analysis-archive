import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("discovery", SCRIPTS / "build_appendix_discovery_tags.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_expected_activity_controls_for_industry_mix():
    # Snack bars sell more transactions per store than restaurants everywhere;
    # area "busy" beats its own mix, "snack" only matches it.
    stores = pd.DataFrame({
        "area_code": ["busy"] * 3 + ["snack"] * 3 + ["base"] * 3,
        "area_type": ["골목상권"] * 9,
        "industry": ["분식", "한식", "치킨"] * 3,
        "stores": [10] * 9,
    })
    tx = {"busy": [400, 200, 200], "snack": [200, 100, 100], "base": [200, 100, 100]}
    sales = pd.DataFrame({
        "area_code": [a for a in tx for _ in range(3)],
        "industry": ["분식", "한식", "치킨"] * 3,
        "transactions": [v for a in tx for v in tx[a]],
    })
    out = MODULE.expected_activity(stores, sales, pd.Index(["busy", "snack", "base"]))
    assert out.loc["busy", "ratio"] == 2.0
    assert out.loc["snack", "ratio"] == 1.0


def test_stable_flag_needs_q4_and_three_quarters():
    panel = pd.DataFrame(
        {20251: [2.0, 2.0, 2.0], 20252: [2.0, 2.0, 0.0], 20253: [2.0, 0.0, 2.0], 20254: [2.0, 2.0, 0.0]},
        index=["all", "three_with_q4", "three_without_q4"],
    )
    flag = MODULE.stable_flag(panel, lambda p: p.ge(1.8))
    assert flag.tolist() == [True, True, False]


def test_entropy_is_low_for_single_industry_areas():
    mix = pd.DataFrame({"a": [10, 5], "b": [0, 5]}, index=["mono", "mixed"])
    h = MODULE.shannon_entropy(mix)
    assert h["mono"] == 0
    assert np.isclose(h["mixed"], np.log(2))


def test_scale_tier_uses_rank_sum_cutoffs():
    n = 20
    stores = pd.Series(range(n), index=[f"a{i}" for i in range(n)], dtype=float).rank(pct=True)
    tier = MODULE.scale_tier(stores, stores)
    assert (tier == "도시핵심").sum() == 2
    assert (tier == "지역핵심").sum() == 3
    assert tier["a19"] == "도시핵심"
