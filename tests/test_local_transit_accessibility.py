import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from local_transit_accessibility import (  # noqa: E402
    build_connections,
    earliest_arrivals,
    parse_gtfs_time,
    select_active_service_ids,
    validate_gtfs,
)


def test_parse_gtfs_time_accepts_service_after_midnight():
    assert parse_gtfs_time("25:01:02") == 25 * 3600 + 62


def test_validate_gtfs_reports_missing_required_file(tmp_path):
    for name in ("stops.txt", "routes.txt", "trips.txt"):
        (tmp_path / name).write_text("id\n", encoding="utf-8")

    with pytest.raises(ValueError, match="stop_times.txt"):
        validate_gtfs(tmp_path)


def test_earliest_arrivals_supports_one_transfer_and_cutoff():
    stop_times = pd.DataFrame(
        [
            {"trip_id": "A", "stop_id": "S1", "stop_sequence": 1, "arrival_time": "08:00:00", "departure_time": "08:00:00"},
            {"trip_id": "A", "stop_id": "S2", "stop_sequence": 2, "arrival_time": "08:10:00", "departure_time": "08:10:00"},
            {"trip_id": "B", "stop_id": "S2", "stop_sequence": 1, "arrival_time": "08:13:00", "departure_time": "08:13:00"},
            {"trip_id": "B", "stop_id": "S3", "stop_sequence": 2, "arrival_time": "08:24:00", "departure_time": "08:24:00"},
            {"trip_id": "B", "stop_id": "S4", "stop_sequence": 3, "arrival_time": "08:40:00", "departure_time": "08:40:00"},
        ]
    )
    connections = build_connections(stop_times)

    arrivals = earliest_arrivals(
        connections,
        access_times={"S1": 0},
        departure_time=parse_gtfs_time("08:00:00"),
        cutoff_seconds=1800,
    )

    assert arrivals["S3"] == parse_gtfs_time("08:24:00")
    assert "S4" not in arrivals


def test_service_calendar_applies_weekday_and_date_exception():
    calendar = pd.DataFrame(
        [
            {
                "service_id": "weekday",
                "monday": "1", "tuesday": "1", "wednesday": "1", "thursday": "1", "friday": "1",
                "saturday": "0", "sunday": "0", "start_date": "20260901", "end_date": "20260930",
            }
        ]
    )
    exceptions = pd.DataFrame(
        [
            {"service_id": "weekday", "date": "20260909", "exception_type": "2"},
            {"service_id": "special", "date": "20260909", "exception_type": "1"},
        ]
    )

    assert select_active_service_ids(calendar, exceptions, "2026-09-09") == {"special"}
