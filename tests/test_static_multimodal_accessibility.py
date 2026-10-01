import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from static_multimodal_accessibility import build_ride_adjacency, filter_active_routes, route_from_access  # noqa: E402


def test_route_from_access_adds_wait_and_transfer_penalty():
    edges = pd.DataFrame(
        [
            {"route_id": "A", "from_stop_id": "S1", "to_stop_id": "S2", "duration_seconds": 300, "mode": "bus"},
            {"route_id": "B", "from_stop_id": "S2", "to_stop_id": "S3", "duration_seconds": 300, "mode": "bus"},
        ]
    )
    adjacency = build_ride_adjacency(edges)

    reached = route_from_access(
        adjacency,
        walking_adjacency={},
        access_times={"S1": 0},
        cutoff_seconds=1800,
        wait_seconds={"bus": 120, "metro": 120},
        transfer_penalty_seconds=180,
    )

    assert reached["S2"] == 420
    assert reached["S3"] == 1020


def test_route_from_access_handles_equal_time_walk_and_ride_states():
    edges = pd.DataFrame(
        [{"route_id": "A", "from_stop_id": "S1", "to_stop_id": "S2", "duration_seconds": 60, "mode": "bus"}]
    )
    reached = route_from_access(
        build_ride_adjacency(edges), {"S1": [("S2", 60)]}, {"S1": 0}, 600,
        {"bus": 0, "metro": 0}, 0,
    )
    assert reached["S2"] == 60


def test_route_specific_wait_overrides_mode_default():
    edges = pd.DataFrame(
        [{"route_id": "slow", "from_stop_id": "S1", "to_stop_id": "S2", "duration_seconds": 60, "mode": "bus"}]
    )
    reached = route_from_access(
        build_ride_adjacency(edges), {}, {"S1": 0}, 600,
        {"bus": 120, "metro": 120}, 0, {"slow": 300},
    )
    assert reached["S2"] == 360


def test_filter_active_routes_removes_bus_without_observed_service():
    edges = pd.DataFrame(
        {"route_id": ["running", "inactive", "metro_line_1"], "mode": ["bus", "bus", "metro"]}
    )
    result = filter_active_routes(edges, {"running": 300, "metro_line_1": 180})
    assert list(result["route_id"]) == ["running", "metro_line_1"]
