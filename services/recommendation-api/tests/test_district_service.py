import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.district_service import build_district_recommendations
from app.live_models import DistrictCandidate, LiveRecommendation


def place(name, duration, distance=1_000):
    return LiveRecommendation(
        place_name=name,
        address="카카오 제공 주소",
        destination_latitude=37.334,
        destination_longitude=127.267,
        expected_travel_time_seconds=duration,
        distance_meters=distance,
    )


def candidate(code, name, recommendation):
    return DistrictCandidate(
        district_code=code,
        district_name=name,
        place=recommendation,
    )


def six_code_distinct_candidates():
    return [
        candidate(
            f"11680{index:05d}",
            f"후보동{index}",
            place(f"후보{index}", index * 60, index * 100),
        )
        for index in range(1, 7)
    ]


def test_same_display_name_with_different_h_codes_stays_separate():
    groups = build_district_recommendations(
        [
            candidate("1168065000", "신사동", place("강남카페", 600)),
            candidate("1162058500", "신사동", place("관악카페", 610)),
        ]
    )

    assert [group.place_count for group in groups] == [1, 1]
    assert len(groups) == 2


def test_same_h_code_groups_places_even_when_addresses_differ():
    groups = build_district_recommendations(
        [
            candidate("1168065000", "신사동", place("빠른카페", 600, 900)),
            candidate("1168065000", "신사동", place("느린카페", 610, 800)),
        ]
    )

    assert groups[0].district_name == "신사동"
    assert groups[0].place_count == 2
    assert [item.place_name for item in groups[0].places] == ["빠른카페", "느린카페"]


def test_orders_places_by_duration_distance_then_name_within_a_district():
    groups = build_district_recommendations(
        [
            candidate("1168065000", "신사동", place("나카페", 300, 1_000)),
            candidate("1168065000", "신사동", place("다카페", 300, 900)),
            candidate("1168065000", "신사동", place("가카페", 300, 900)),
        ]
    )

    assert [item.place_name for item in groups[0].places] == [
        "가카페",
        "다카페",
        "나카페",
    ]


def test_orders_district_ties_by_count_distance_then_name():
    groups = build_district_recommendations(
        [
            candidate("1", "가나다동", place("가", 600, 200)),
            candidate("2", "라마다동", place("나", 600, 100)),
            candidate("3", "사아동", place("다", 600, 100)),
            candidate("4", "자차동", place("라", 600, 300)),
            candidate("4", "자차동", place("마", 700, 100)),
        ]
    )

    assert [group.district_name for group in groups] == [
        "자차동",
        "라마다동",
        "사아동",
        "가나다동",
    ]


def test_group_cap_cannot_exceed_five_when_codes_are_distinct():
    assert len(build_district_recommendations(six_code_distinct_candidates(), 99)) == 5


def test_group_cap_has_a_minimum_of_one_district():
    assert len(build_district_recommendations(six_code_distinct_candidates(), 0)) == 1
