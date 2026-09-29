import geopandas as gpd
import pandas as pd
import subprocess
import sys
from shapely.geometry import Polygon


def test_scope_nightlife_pois_counts_cooking_pubs_but_keeps_adult_venues_out_of_score():
    from scripts.build_nightlife_poi_scope import scope_nightlife_pois

    areas = gpd.GeoDataFrame(
        {"area_code": ["1", "2"], "area_name": ["가", "나"]},
        geometry=[
            Polygon([(126.0, 37.0), (126.01, 37.0), (126.01, 37.01), (126.0, 37.01)]),
            Polygon([(126.02, 37.0), (126.03, 37.0), (126.03, 37.01), (126.02, 37.01)]),
        ],
        crs="EPSG:4326",
    )
    places = pd.DataFrame(
        {
            "place_id": ["a", "b", "c"],
            "venue_class": ["night_food", "adult_nightlife", "night_food"],
            "longitude": [126.005, 126.025, 126.1],
            "latitude": [37.005, 37.005, 37.1],
        }
    )

    detail, features = scope_nightlife_pois(places, areas)

    assert len(detail) == 3
    assert detail.loc[detail.place_id == "a", "scope_status"].iat[0] == "INSIDE_OFFICIAL_AREA"
    assert detail.loc[detail.place_id == "c", "scope_status"].iat[0] == "OUTSIDE_SELECTED_AREA"
    first = features.loc[features.area_code == "1"].iloc[0]
    assert first.night_food_inside_count == 1
    assert first.adult_nightlife_inside_count == 0
    second = features.loc[features.area_code == "2"].iloc[0]
    assert second.night_food_inside_count == 0
    assert second.adult_nightlife_inside_count == 1


def test_nightlife_collector_can_be_invoked_directly():
    result = subprocess.run(
        [sys.executable, "scripts/collect_kakao_nightlife_pois.py", "--help"],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
