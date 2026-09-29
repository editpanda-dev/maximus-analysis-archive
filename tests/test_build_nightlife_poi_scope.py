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
    assert detail.loc[detail.place_id == "c", "nearest_area_code"].iat[0] == "2"
    assert detail.loc[detail.place_id == "c", "euclidean_distance_m"].iat[0] > 400
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


class _KeywordResponse:
    def __init__(self, page):
        self.page = page

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "documents": [{"id": f"p{self.page}-{i}", "x": "127", "y": "37"} for i in range(15)],
            "meta": {"is_end": False},
        }


class _KeywordClient:
    def __init__(self):
        self.calls = []

    def get(self, url, headers, params):
        self.calls.append(params)
        return _KeywordResponse(params["page"])


def test_keyword_collector_marks_a_tile_truncated_when_page_three_is_not_end():
    from scripts.collect_kakao_nightlife_pois import fetch_tile

    items, audit = fetch_tile(_KeywordClient(), "key", "night_food", (126, 37, 127, 38), 0)

    assert len(items) == 45
    assert audit["truncated"] is True
    assert audit["document_count"] == 45
