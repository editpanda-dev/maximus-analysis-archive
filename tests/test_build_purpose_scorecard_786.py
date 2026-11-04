import importlib.util
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("purpose_scorecard", SCRIPTS / "build_purpose_scorecard_786.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _purpose(scores, status=None, eligible=None, name="x"):
    idx = pd.Index([f"a{i}" for i in range(len(scores))], name="area_code")
    return pd.DataFrame({
        f"{name}_score": scores,
        f"{name}_status": status or ["full"] * len(scores),
        f"{name}_eligible": eligible or [True] * len(scores),
        f"{name}_source_status": "official_v2",
    }, index=idx)


def test_combo_requires_floor_full_basis_and_eligibility():
    n = 6
    base = pd.DataFrame({
        "area_code": [f"a{i}" for i in range(n)], "area_name": [f"n{i}" for i in range(n)], "area_type_name": "골목상권",
        "recommendation_eligible": [True] * 5 + [False], "is_tourism_zone": [False] * 5 + [True], "small_area": False,
    })
    purposes = {
        "food": _purpose([90, 80, 70, 85, 10, 99], status=["full", "full", "supply_only", "full", "full", "full"], name="food"),
        "cafe": _purpose([90, 10, 80, 95, 90, 99], name="cafe"),
    }
    card = MODULE.build(base, purposes)
    geom = gpd.GeoSeries({f"a{i}": box(i * 10, 0, i * 10 + 5, 5) for i in range(n)}, crs=5181)
    combos = MODULE.combo_tables(card, geom, ["food", "cafe"])
    # a1 weak cafe, a2 supply-only food, a4 weak food, a5 tourism -> only a0 and a3 qualify
    assert sorted(combos.area_code) == ["a0", "a3"]
    assert (combos[["food_pct", "cafe_pct"]] >= MODULE.COMBO_MIN_PERCENTILE).all().all()
