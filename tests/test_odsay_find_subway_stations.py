import importlib.util
import sys
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("odsay_find_subway_stations", SCRIPTS / "odsay_find_subway_stations.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}


def test_point_in_geometry():
    assert module.point_in_geometry(1, 1, SQUARE)
    assert not module.point_in_geometry(3, 1, SQUARE)
    assert module.boundary_distance_m(2.00001, 1, SQUARE) < 2


def test_physical_stations_merges_same_station_lines():
    payload = {"result": {"station": [
        {"stationClass": 2, "stationName": "회기역", "stationID": 1, "x": 1, "y": 1, "laneName": "1호선"},
        {"stationClass": 2, "stationName": "회기역", "stationID": 2, "x": 1.01, "y": 1.01, "laneName": "경의중앙선"},
        {"stationClass": 2, "stationName": "밖역", "stationID": 3, "x": 3, "y": 3, "laneName": "2호선"},
    ]}}
    rows = module.physical_stations(payload, SQUARE)
    assert len(rows) == 1
    assert rows[0]["odsay_station_ids"] == "1|2"
    assert rows[0]["lines"] == "1호선|경의중앙선"
