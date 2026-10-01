import pandas as pd
import pytest

shapely = pytest.importorskip("shapely")
from shapely.geometry import Point, mapping, Polygon

from scripts.validate_static_vs_odsay import compare_origin, isochrone_geometry


def test_isochrone_geometry_unions_feature_geometries():
    payload = {
        "result": {"geojson": {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": mapping(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])), "properties": {}},
            {"type": "Feature", "geometry": mapping(Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])), "properties": {}},
        ]}}
    }
    geom = isochrone_geometry(payload)
    assert geom.contains(Point(.5, .5))
    assert geom.contains(Point(2.5, .5))


def test_compare_origin_reports_set_overlap_metrics():
    stops = pd.DataFrame({
        "stop_id": ["a", "b", "c"], "longitude": [0.5, 2.5, 4.0], "latitude": [.5, .5, .5],
    })
    static = pd.DataFrame({"origin_id": ["origin", "origin"], "stop_id": ["a", "c"]})
    payload = {"result": {"geojson": {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": mapping(Polygon([(0, 0), (3, 0), (3, 1), (0, 1)])), "properties": {}},
    ]}}}
    result = compare_origin("origin", stops, static, payload)
    assert result["true_positive_stops"] == 1
    assert result["false_positive_stops"] == 1
    assert result["false_negative_stops"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["jaccard"] == 1 / 3
