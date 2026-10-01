import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from calibrate_transit_times import (  # noqa: E402
    bus_route_waits,
    metro_line_waits,
    weighted_transfer_median,
)


def test_bus_route_wait_is_half_observed_headway():
    frame = pd.DataFrame({"노선_ID": [1, 1, 2], "버스운행횟수_08시": [4, 4, 10]})
    result = bus_route_waits(frame, 8).set_index("route_id")
    assert result.loc["1", "wait_seconds"] == 450
    assert result.loc["2", "wait_seconds"] == 180


def test_metro_wait_is_half_median_departure_gap():
    frame = pd.DataFrame(
        {
            "line": ["1"] * 3, "stop_id": ["S"] * 3, "service_type": ["DAY"] * 3,
            "departure_time": ["08:00:00", "08:06:00", "08:12:00"],
        }
    )
    result = metro_line_waits(frame, 8).set_index("route_id")
    assert result.loc["metro_line_1", "wait_seconds"] == 180


def test_transfer_median_is_weighted_by_observed_transfers():
    frame = pd.DataFrame({"시간대": ["08", "08"], "환승_수_합": [9, 1], "환승_시간_평균": [240, 900]})
    assert weighted_transfer_median(frame, 8) == 240
