import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"status": "OK", "route": {"properties": {"totalDistance": 350, "totalTime": 300}}}


class _Session:
    def __init__(self):
        self.calls = []

    def get(self, url, headers, params, timeout):
        self.calls.append(params)
        return _Response()


def _areas():
    return gpd.GeoDataFrame(
        {"area_code": ["1", "2"], "area_name": ["가", "나"]},
        geometry=[
            Polygon([(127.0, 37.5), (127.001, 37.5), (127.001, 37.501), (127.0, 37.501)]),
            Polygon([(127.01, 37.5), (127.011, 37.5), (127.011, 37.501), (127.01, 37.501)]),
        ],
        crs="EPSG:4326",
    )


def test_walk_access_calls_api_only_for_external_candidates_within_straight_line_limit():
    from scripts.enrich_nightlife_walk_access import build_walk_access

    queue = pd.DataFrame({
        "place_id": ["inside", "near", "far"],
        "venue_class": ["night_food", "night_food", "adult_nightlife"],
        "longitude": [127.0005, 127.002, 127.1],
        "latitude": [37.5005, 37.5005, 37.6],
        "scope_status": ["INSIDE_OFFICIAL_AREA", "OUTSIDE_SELECTED_AREA", "OUTSIDE_SELECTED_AREA"],
        "area_code": ["1", None, None],
        "nearest_area_code": ["1", "1", "2"],
        "euclidean_distance_m": [0.0, 100.0, 1000.0],
    })
    session = _Session()

    result = build_walk_access(queue, _areas(), "key", session=session, sleep_seconds=0)

    assert len(session.calls) == 1
    assert result.set_index("place_id").loc["inside", "route_status"] == "INSIDE_OFFICIAL_AREA"
    assert result.set_index("place_id").loc["near", "walk_access_400"]
    assert result.set_index("place_id").loc["far", "route_status"] == "EUCLIDEAN_GT_400"
    assert not result.set_index("place_id").loc["far", "walk_access_400"]


def test_aggregate_keeps_night_food_and_adult_counts_separate_for_all_areas():
    from scripts.enrich_nightlife_walk_access import aggregate_walk_features

    detail = pd.DataFrame({
        "place_id": ["a", "b", "c"],
        "venue_class": ["night_food", "adult_nightlife", "night_food"],
        "target_area_code": ["1", "1", "2"],
        "walk_access_400": [True, True, False],
    })
    features = aggregate_walk_features(detail, _areas())

    first = features.set_index("area_code").loc["1"]
    second = features.set_index("area_code").loc["2"]
    assert first.night_food_walk400_count == 1
    assert first.adult_nightlife_walk400_count == 1
    assert second.night_food_walk400_count == 0
    assert len(features) == 2
