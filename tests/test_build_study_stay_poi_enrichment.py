import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

from scripts.build_study_stay_poi_enrichment import (
    build_study_stay_enrichment,
    map_pois_to_areas,
)


def test_map_pois_to_areas_counts_study_cafes_and_starbucks_inside_each_polygon():
    areas = gpd.GeoDataFrame(
        {"area_code": ["a", "b"]},
        geometry=[
            Polygon([(126.0, 37.0), (126.1, 37.0), (126.1, 37.1), (126.0, 37.1)]),
            Polygon([(126.1, 37.0), (126.2, 37.0), (126.2, 37.1), (126.1, 37.1)]),
        ],
        crs="EPSG:4326",
    )
    pois = pd.DataFrame({
        "place_id": ["s1", "s2", "c1"],
        "place_type": ["study_cafe", "study_cafe", "starbucks"],
        "longitude": [126.05, 126.15, 126.15],
        "latitude": [37.05, 37.05, 37.05],
    })

    result = map_pois_to_areas(areas, pois)

    first = result[result.area_code == "a"].iloc[0]
    second = result[result.area_code == "b"].iloc[0]
    assert first.study_cafe_inside_count == 1
    assert first.starbucks_inside_count == 0
    assert second.study_cafe_inside_count == 1
    assert second.starbucks_inside_count == 1


def test_study_stay_score_rewards_study_cafes_large_cafes_and_accessibility():
    rankings = pd.DataFrame({
        "area_code": ["a", "b", "a", "b"],
        "purpose": ["공부", "공부", "카페", "카페"],
        "purpose_store_count": [2, 2, 10, 10],
        "minimum_period_ratio": [0.8, 0.8, 0.8, 0.8],
    })
    poi_features = pd.DataFrame({
        "area_code": ["a", "b"],
        "area_km2": [1.0, 1.0],
        "study_cafe_inside_count": [0, 3],
        "starbucks_inside_count": [0, 1],
    })

    result = build_study_stay_enrichment(rankings, poi_features)

    assert result.iloc[0].area_code == "b"
    assert {"study_cafe_percentile", "starbucks_percentile", "cafe_supply_percentile", "study_stay_current_score"}.issubset(result.columns)


def test_study_stay_score_uses_density_so_large_polygons_do_not_win_by_area():
    rankings = pd.DataFrame({
        "area_code": ["small", "large", "small", "large"],
        "purpose": ["공부", "공부", "카페", "카페"],
        "purpose_store_count": [2, 2, 10, 10],
        "minimum_period_ratio": [0.8, 0.8, 0.8, 0.8],
    })
    poi_features = pd.DataFrame({
        "area_code": ["small", "large"],
        "area_km2": [1.0, 10.0],
        "study_cafe_inside_count": [2, 2],
        "starbucks_inside_count": [1, 1],
    })

    result = build_study_stay_enrichment(rankings, poi_features)

    assert result.iloc[0].area_code == "small"
