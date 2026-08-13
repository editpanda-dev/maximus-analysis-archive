import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.district_service import (
    build_district_recommendations,
    extract_administrative_district,
)
from app.live_models import LiveRecommendation


def place(name, address, duration, distance):
    return LiveRecommendation(
        place_name=name,
        address=address,
        destination_latitude=37.334,
        destination_longitude=127.267,
        expected_travel_time_seconds=duration,
        distance_meters=distance,
    )


def six_distinct_places():
    return [
        place(
            f"후보{index}",
            f"경기 용인시 처인구 {district} 1",
            index * 60,
            index * 100,
        )
        for index, district in enumerate(
            ("일동", "이동", "삼동", "사동", "오동", "육동"), start=1
        )
    ]


def test_extracts_administrative_district_from_korean_address():
    assert (
        extract_administrative_district("경기 용인시 처인구 모현읍 외대로 42-1")
        == "모현읍"
    )
    assert (
        extract_administrative_district("서울 송파구 가락1동 송파대로 55")
        == "가락1동"
    )


def test_rejects_non_korean_or_number_only_district_like_tokens():
    assert extract_administrative_district("경기 용인시 A동 외대로 1") is None
    assert extract_administrative_district("경기 용인시 123동 외대로 1") is None
    assert extract_administrative_district("not-an-address동") is None


def test_unparseable_address_is_not_assigned_to_a_district():
    assert extract_administrative_district("주소 정보 없음") is None
    assert build_district_recommendations(
        [place("알수없음", "주소 정보 없음", 60, 100)]
    ) == []


def test_groups_mohyeon_eup_places_and_orders_by_fastest_then_count():
    districts = build_district_recommendations(
        [
            place("썸카페", "경기 용인시 처인구 모현읍 외대로 42-1", 547, 1194),
            place("이디야", "경기 용인시 처인구 모현읍 외대로 36", 552, 1202),
            place("죽전카페", "경기 용인시 수지구 죽전동 123", 540, 1400),
        ]
    )

    assert [district.district_name for district in districts] == ["죽전동", "모현읍"]
    assert districts[1].place_count == 2


def test_orders_places_by_duration_distance_then_name_within_a_district():
    districts = build_district_recommendations(
        [
            place("나카페", "경기 용인시 수지구 죽전동 1", 300, 1000),
            place("다카페", "경기 용인시 수지구 죽전동 2", 300, 900),
            place("가카페", "경기 용인시 수지구 죽전동 3", 300, 900),
        ]
    )

    assert [place.place_name for place in districts[0].places] == [
        "가카페",
        "다카페",
        "나카페",
    ]


def test_orders_district_ties_by_count_distance_then_name():
    districts = build_district_recommendations(
        [
            place("가", "경기 용인시 처인구 가나다동 1", 600, 200),
            place("나", "경기 용인시 처인구 라마다동 1", 600, 100),
            place("다", "경기 용인시 처인구 사아동 1", 600, 100),
            place("라", "경기 용인시 처인구 자차동 1", 600, 300),
            place("마", "경기 용인시 처인구 자차동 2", 700, 100),
        ]
    )

    assert [district.district_name for district in districts] == [
        "자차동",
        "라마다동",
        "사아동",
        "가나다동",
    ]


def test_group_cap_cannot_be_overridden_above_five():
    districts = build_district_recommendations(six_distinct_places(), maximum_districts=99)

    assert len(districts) == 5


def test_group_cap_has_a_minimum_of_one_district():
    districts = build_district_recommendations(six_distinct_places(), maximum_districts=0)

    assert len(districts) == 1
