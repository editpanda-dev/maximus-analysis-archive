import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_seoul_transit_network import (  # noqa: E402
    build_bus_edges,
    build_metro_edges,
    build_metro_stops,
    convert_metro_timetable,
)


def test_build_bus_edges_keeps_route_adjacency_and_hour_duration():
    route_stops = pd.DataFrame(
        {
            "ROUTE_ID": [10, 10, 10],
            "노선명": ["A", "A", "A"],
            "순번": [1, 2, 3],
            "NODE_ID": [100, 101, 102],
            "정류소명": ["가", "나", "다"],
            "X좌표": [127.0, 127.01, 127.02],
            "Y좌표": [37.5, 37.51, 37.52],
        }
    )
    speeds = pd.DataFrame(
        {
            "노선_ID": [10, 10, 10],
            "출발_정류장_ID": [100, 100, 101],
            "도착_정류장_ID": [101, 101, 102],
            "운행시간_10시": [60, 120, 90],
        }
    )

    edges = build_bus_edges(route_stops, speeds, hour=10)

    assert list(edges["duration_seconds"]) == [90.0, 90.0]
    assert list(edges["from_stop_id"]) == ["100", "101"]


def test_convert_metro_timetable_creates_unique_trip_and_gtfs_times():
    raw = pd.DataFrame(
        {
            "호선": ["1", "1"], "역사코드": ["0150", "0151"], "역사명": ["서울역", "시청"],
            "주중주말": ["DAY", "DAY"], "방향": ["UP", "UP"], "급행여부": ["0", "0"],
            "열차코드": ["K1", "K1"], "열차도착시간": ["05:00:00", "05:03:00"],
            "열차출발시간": ["05:00:30", "05:03:30"], "출발역": ["서울역", "서울역"], "도착역": ["청량리", "청량리"],
        }
    )

    result = convert_metro_timetable(raw)

    assert result["trip_id"].nunique() == 1
    assert list(result["stop_sequence"]) == [1, 2]
    assert result.loc[0, "stop_id"] == "metro_1_0150"


def test_build_metro_stops_matches_station_code_and_line():
    master = pd.DataFrame(
        {"역사_ID": [150, 201], "역사명": ["서울역", "시청"], "호선": ["1호선", "2호선"], "위도": [37.55, 37.56], "경도": [126.97, 126.98]}
    )
    timetable = pd.DataFrame({"stop_id": ["metro_1_0150"], "line": ["1"], "stop_name": ["서울역"]})

    result = build_metro_stops(master, timetable)

    assert result.loc[0, "stop_id"] == "metro_1_0150"
    assert result.loc[0, "longitude"] == 126.97


def test_build_metro_stops_falls_back_to_unambiguous_station_name():
    master = pd.DataFrame(
        {"역사_ID": [1017], "역사명": ["신이문"], "호선": ["경원선"], "위도": [37.6018], "경도": [127.0672]}
    )
    timetable = pd.DataFrame({"stop_id": ["metro_1_1017"], "line": ["1"], "stop_name": ["신이문"]})

    result = build_metro_stops(master, timetable)

    assert result.loc[0, "stop_id"] == "metro_1_1017"


def test_build_metro_edges_uses_consecutive_weekday_stops():
    timetable = pd.DataFrame(
        {
            "trip_id": ["T", "T"], "stop_id": ["M1", "M2"], "line": ["1", "1"],
            "service_type": ["DAY", "DAY"], "departure_time": ["10:00:30", "10:03:30"],
            "arrival_time": ["10:00:00", "10:03:00"], "stop_sequence": [1, 2],
        }
    )

    edges = build_metro_edges(timetable)

    assert edges.loc[0, "duration_seconds"] == 150
