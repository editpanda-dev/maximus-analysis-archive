import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_food_shopping_size_neutral.py"
SPEC = importlib.util.spec_from_file_location("food_shopping", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_assign_point_group_separates_meals_bars_cafes_and_daily_shopping():
    assert MODULE.assign_point_group("음식", "한식", "백반/한정식") == "food_meal"
    assert MODULE.assign_point_group("음식", "주점", "요리 주점") == "food_bar"
    assert MODULE.assign_point_group("음식", "비알코올 ", "카페") is None
    assert MODULE.assign_point_group("음식", "기타 간이", "빵/도넛") is None
    assert MODULE.assign_point_group("음식", "구내식당·뷔페", "구내식당") is None
    assert MODULE.assign_point_group("음식", "구내식당·뷔페", "뷔페") == "food_meal"
    assert MODULE.assign_point_group("소매", "종합 소매", "편의점") == "shopping_daily"
    assert MODULE.assign_point_group("소매", "섬유·의복·신발 소매", "남성 의류 소매업") == "shopping_destination"
    assert MODULE.assign_point_group("소매", "의약·화장품 소매", "화장품 소매업") == "shopping_destination"
    assert MODULE.assign_point_group("소매", "의약·화장품 소매", "약국") == "shopping_daily"
    assert "제과점" not in MODULE.AREA_SALES_INDUSTRIES["food_meal"]
    assert MODULE.assign_point_group("부동산", "부동산 서비스", "부동산 중개/대리업") is None


def test_shrunk_location_quotient_pulls_tiny_areas_toward_one():
    lq = MODULE.shrunk_location_quotient(pd.Series([2, 200]), pd.Series([2, 200]), city_share=0.2)
    assert lq.iloc[0] < lq.iloc[1]
    assert 1 < lq.iloc[0] < 5


def test_productivity_signal_drops_low_coverage_areas():
    out = MODULE.productivity_signal(
        sales=pd.Series([100.0, 100.0, 0.0]),
        disclosed_stores=pd.Series([10, 2, 0]),
        purpose_stores=pd.Series([10, 10, 3]),
    )
    assert out.sales_per_store.notna().tolist() == [True, False, False]
    assert np.isclose(out.sales_coverage.iloc[1], 0.2)


def test_flag_wholesale_uses_city_median_and_minimum_size():
    rows = pd.DataFrame(
        {
            "area_code": ["M", "A", "B", "C", "tiny"],
            "area_type": ["발달상권"] * 5,
            "industry": ["수산물판매"] * 5,
            "stores": [100, 10, 10, 10, 2],
            "sales": [100 * 100.0, 10 * 10.0, 10 * 10.0, 10 * 10.0, 2 * 1000.0],
        }
    )
    flags = MODULE.flag_wholesale(rows)
    assert flags.index.tolist() == ["M"]


def test_flag_wholesale_ignores_department_store_apparel_outside_markets():
    rows = pd.DataFrame(
        {
            "area_code": ["dept", "market", "A", "B", "C"],
            "area_type": ["발달상권", "전통시장", "골목상권", "골목상권", "골목상권"],
            "industry": ["일반의류"] * 5,
            "stores": [50, 50, 10, 10, 10],
            "sales": [50 * 100.0, 50 * 100.0, 10 * 10.0, 10 * 10.0, 10 * 10.0],
        }
    )
    assert MODULE.flag_wholesale(rows).index.tolist() == ["market"]


def test_count_points_uses_common_buffer_footprint():
    areas = gpd.GeoDataFrame({"area_code": ["small", "large"]}, geometry=[box(0, 0, 10, 10), box(1000, 0, 1500, 500)], crs=5181)
    points = gpd.GeoDataFrame(
        {"group": ["food_meal", "food_meal", "food_meal"]},
        geometry=[Point(5, 5), Point(200, 5), Point(1200, 200)],
        crs=5181,
    )
    counts = MODULE.count_points(points, areas, buffer_m=400)
    assert counts.loc["small", "food_meal_inside_count"] == 1
    assert counts.loc["small", "food_meal_buffer400_count"] == 2
    assert counts.loc["large", "food_meal_buffer400_count"] == 1
    assert counts.loc["small", "footprint_km2"] > counts.loc["small", "polygon_km2"] * 100
