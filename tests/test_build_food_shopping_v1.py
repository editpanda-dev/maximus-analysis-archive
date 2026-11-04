import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_food_shopping_v1.py"
SPEC = importlib.util.spec_from_file_location("food_shopping_v1", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_each_code_belongs_to_one_subtype_and_no_other_purpose():
    sbiz = [c for rule in MODULE.SUBTYPES.values() for c in rule["sbiz"]]
    industries = [c for rule in MODULE.SUBTYPES.values() for c in rule["industries"]]
    assert len(sbiz) == len(set(sbiz))
    assert len(industries) == len(set(industries))
    assert not set(sbiz) & MODULE.OTHER_PURPOSE_SBIZ
    assert not set(industries) & MODULE.OTHER_PURPOSE_INDUSTRIES
    assert MODULE.SBIZ_TO_SUBTYPE["I20101"] == "M1"
    assert MODULE.SBIZ_TO_SUBTYPE["I21006"] == "M6"
    assert "I21001" not in MODULE.SBIZ_TO_SUBTYPE  # bakery -> cafe
    assert "I21104" not in MODULE.SBIZ_TO_SUBTYPE  # bar -> leisure
    assert "SH5" not in MODULE.PURPOSES["shopping"]["subtypes"]


def test_shrunk_location_quotient_pulls_tiny_areas_toward_one():
    lq = MODULE.shrunk_location_quotient(pd.Series([2, 200]), pd.Series([2, 200]), city_share=0.2)
    assert lq.iloc[0] < lq.iloc[1]
    assert 1 < lq.iloc[0] < 5


def test_productivity_signal_uses_three_sales_levels():
    out = MODULE.productivity_signal(
        sales=pd.Series([100.0, 100.0, 100.0, 0.0]),
        expected_sales=pd.Series([100.0, 50.0, 100.0, 0.0]),
        disclosed_stores=pd.Series([8, 4, 2, 0]),
        purpose_stores=pd.Series([10, 10, 10, 3]),
    )
    assert out.sales_status.tolist() == ["observed", "estimated", "missing", "missing"]
    assert out.sales_index.notna().tolist() == [True, True, False, False]
    assert out.sales_index.iloc[1] == 2.0  # twice what the same industry mix sells in Seoul


def test_missing_sales_use_supply_only_without_neutral_fill():
    n = 6
    features = pd.DataFrame(
        {
            "polygon_km2": np.linspace(0.05, 0.3, n),
            "footprint_km2": np.linspace(1.0, 2.0, n),
            "M1_inside_count": [1, 5, 10, 20, 40, 80],
            "M1_walk_count": [10, 20, 40, 80, 160, 320],
            "all_walk_count": [100] * n,
            "M1_sales_index": [np.nan, 1.0, 2.0, np.nan, 4.0, 5.0],
        },
        index=pd.Index(list("abcdef"), name="area_code"),
    )
    out = MODULE.score_unit(features, "M1", city_share=0.2)
    missing = out.M1_score_basis == "supply_only"
    assert missing.tolist() == [True, False, False, True, False, False]
    assert (out.loc[missing, "M1_score"] == out.loc[missing, "M1_supply"]).all()
    assert out.M1_score.between(0, 100).all()


def test_wholesale_candidates_need_review_and_skip_department_stores():
    rows = pd.DataFrame(
        {
            "area_code": ["dept", "market", "A", "B", "C", "fish", "D", "E", "F"],
            "area_type": ["발달상권", "전통시장", "골목상권", "골목상권", "골목상권", "발달상권", "골목상권", "골목상권", "골목상권"],
            "industry": ["일반의류"] * 5 + ["수산물판매"] * 4,
            "stores": [50, 50, 10, 10, 10, 100, 10, 10, 10],
            "sales": [50 * 100.0, 50 * 100.0, 100.0, 100.0, 100.0, 100 * 100.0, 100.0, 100.0, 100.0],
        }
    )
    candidates = MODULE.flag_wholesale_candidates(rows)
    assert sorted(candidates.index) == ["fish", "market"]
    with pytest.raises(ValueError):
        MODULE.apply_wholesale_review(candidates, pd.DataFrame({"area_code": ["fish"], "review_decision": ["retail"], "review_note": [""]}))
    review = pd.DataFrame(
        {"area_code": ["fish", "market"], "review_decision": ["wholesale_food", "retail"], "review_note": ["", ""]}
    )
    decided = MODULE.apply_wholesale_review(candidates, review)
    assert decided.loc["fish", "wholesale_decision"] == "wholesale_food"
    assert MODULE.WHOLESALE_EFFECT["wholesale_apparel"] == ["shopping", "SH1"]


def test_count_points_includes_boundary_and_buffer():
    areas = gpd.GeoDataFrame({"area_code": ["small", "large"]}, geometry=[box(0, 0, 10, 10), box(1000, 0, 1500, 500)], crs=5181)
    points = gpd.GeoDataFrame(
        {"subtype": ["M1", "M1", "M1", "M1"]},
        geometry=[Point(5, 5), Point(10, 5), Point(200, 5), Point(1200, 200)],
        crs=5181,
    )
    counts = MODULE.count_points(points, areas, buffer_m=400)
    assert counts.loc["small", "M1_inside_count"] == 2  # boundary point kept
    assert counts.loc["small", "M1_walk_count"] == 3
    assert counts.loc["large", "M1_walk_count"] == 1


def test_pick_top_skips_overlapping_lower_rank():
    geom = gpd.GeoSeries({"a": box(0, 0, 10, 10), "b": box(1, 1, 9, 9), "c": box(100, 100, 110, 110)}, crs=5181)
    frame = pd.DataFrame({"score": [90, 80, 70]}, index=pd.Index(["a", "b", "c"], name="area_code"))
    top = MODULE.pick_top(frame, "score", geom, n=2)
    assert top.index.tolist() == ["a", "c"]
    assert top.attrs["skipped_overlap"] == {"b": "a"}


def test_josa_picks_particle_from_last_hangul_syllable():
    assert MODULE.josa("종로3가역", "은", "는") == "은"
    assert MODULE.josa("인사동", "은", "는") == "은"
    assert MODULE.josa("서울숲카페거리", "은", "는") == "는"
    assert MODULE.josa("경동광성상가(경동시장)", "은", "는") == "는"


def test_zero_stores_get_zero_supply_percentile():
    features = pd.DataFrame(
        {
            "polygon_km2": [0.1] * 5,
            "footprint_km2": [1.0] * 5,
            "M2_inside_count": [0, 0, 0, 3, 6],
            "M2_walk_count": [0, 4, 8, 12, 16],
            "all_walk_count": [100] * 5,
            "M2_sales_index": [np.nan] * 5,
        },
        index=pd.Index(list("abcde"), name="area_code"),
    )
    out = MODULE.score_unit(features, "M2", city_share=0.05)
    assert (out.loc[["a", "b", "c"], "M2_p_inside_density"] == 0).all()
    assert out.loc["a", "M2_p_walk_density"] == 0
    assert out.loc["a", "M2_supply"] < out.loc["e", "M2_supply"]


def test_reason_names_supply_strength_only_when_high():
    base = {
        "area_name": "인사동", "food_score": 60.0, "food_top_subtypes": "", "food_sales_status": "observed",
        "minimum_period_ratio": 0.95, "wholesale_decision": "retail",
        "food_p_inside_density": 55.0, "food_p_walk_density": 40.0, "food_p_lq": 30.0,
    }
    weak = MODULE.purpose_reason(pd.Series(base), "food")
    strong = MODULE.purpose_reason(pd.Series({**base, "food_p_inside_density": 90.0}), "food")
    assert "촘촘히" not in weak
    assert "촘촘히" in strong


def test_count_points_uses_walk_routes_for_outside_stores():
    areas = gpd.GeoDataFrame({"area_code": ["a"]}, geometry=[box(0, 0, 100, 100)], crs=5181)
    points = gpd.GeoDataFrame(
        {"subtype": ["M1"] * 4, "cell_id": ["in", "near", "detour", "unknown"]},
        geometry=[Point(50, 50), Point(150, 50), Point(300, 50), Point(350, 50)],
        crs=5181,
    )
    routes = pd.DataFrame({"area_code": ["a", "a"], "cell_id": ["near", "detour"], "walk_distance_m": [60.0, 650.0]})
    counts = MODULE.count_points(points, areas, buffer_m=400, walk_routes=routes)
    # inside + near walk route + unknown (straight-line fallback); the 650m detour is dropped
    assert counts.loc["a", "M1_walk_count"] == 3
    assert np.isclose(counts.loc["a", "walk_route_coverage"], 2 / 3)


def test_lunch_price_tier_is_relative_to_industry_and_needs_volume():
    sales = pd.DataFrame({
        "area_code": [f"a{i}" for i in range(8)],
        "industry": ["한식음식점"] * 4 + ["분식전문점"] * 4,
        MODULE.LUNCH_AMOUNT: [1000 * 20000, 1000 * 25000, 1000 * 30000, 10 * 90000, 1000 * 5000, 1000 * 6000, 1000 * 7000, 1000 * 8000],
        MODULE.LUNCH_COUNT: [1000, 1000, 1000, 10, 1000, 1000, 1000, 1000],
    })
    cells = MODULE.lunch_price_cells(sales).set_index("area_code")
    # an 8,000-won snack bar is pricier than its peers, a 20,000-won Korean meal is cheaper than its peers
    assert cells.loc["a7", "lunch_price_index"] > 1 > cells.loc["a0", "lunch_price_index"]
    tiers = MODULE.price_tier(cells.lunch_price_index, cells.lunch_tx >= MODULE.PRICE_MIN_LUNCH_TX)
    assert tiers["a3"] == "정보없음"  # 10 lunch transactions
