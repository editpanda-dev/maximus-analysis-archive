import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import Polygon

from scripts.build_commercial_area_accessibility import (
    access_tier,
    build_area_dong_overlap,
    normalize_area_code,
    prepare_dong_boundaries,
)


def test_access_tier_uses_worst_period_threshold():
    assert access_tier(0.81) == "core_80pct_all_periods"
    assert access_tier(0.50) == "base_50pct_all_periods"
    assert access_tier(0.25) == "exploration_25pct_all_periods"
    assert access_tier(0.249) == "excluded_below_25pct"


def test_area_code_is_stable_string():
    assert normalize_area_code(3110008.0) == "3110008"


def test_area_dong_overlap_keeps_cross_boundary_share():
    area = gpd.GeoDataFrame({"area_code": ["3000001"], "area_name": ["A"], "area_type_name": ["골목상권"]}, geometry=[Polygon([(0, 0), (2, 0), (2, 1), (0, 1)])], crs=5181)
    dongs = gpd.GeoDataFrame({"admin_code": ["11111111", "22222222"], "admin_name": ["가", "나"], "district_name": ["구", "구"]}, geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])], crs=5181)
    result = build_area_dong_overlap(area, dongs)
    assert len(result) == 2
    assert result.overlap_share.sum() == pytest.approx(1.0)


def test_dong_boundaries_keep_official_and_spatial_code_systems_separate():
    dongs = gpd.GeoDataFrame(
        {
            "emd8": ["11060710"],
            "emdcd": ["1123071000"],
            "emdnm": ["회기동"],
            "sggnm": ["동대문구"],
        },
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs=5181,
    )

    result = prepare_dong_boundaries(dongs)

    assert result.loc[0, "admin_code"] == "11230710"
    assert result.loc[0, "spatial_admin_code"] == "11060710"
