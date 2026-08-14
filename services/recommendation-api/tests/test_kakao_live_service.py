import asyncio
import sys
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.kakao_client import KakaoClient
from app.live_models import (
    KakaoAdministrativeDistrict,
    KakaoPlace,
    KakaoTransitRoute,
    LiveRecommendationRequest,
    RouteStep,
)
from app.live_service import KakaoTransitRecommendationService


def run(coroutine):
    return asyncio.run(coroutine)


def valid_request(**overrides):
    data = {
        "origin_name": "한국외국어대학교 글로벌캠퍼스",
        "origin_latitude": 37.334,
        "origin_longitude": 127.267,
        "purpose": "cafe",
        "max_travel_time_minutes": 30,
    }
    data.update(overrides)
    return LiveRecommendationRequest(**data)


class StubKakaoClient:
    def __init__(self, places=(), routes=None, districts=None):
        self.places = list(places)
        self.routes = routes or {}
        self.districts = districts or {}
        self.searches = []
        self.route_requests = []
        self.district_lookup_coordinates = []

    async def search_places(self, *, keyword, longitude, latitude):
        self.searches.append(
            {"keyword": keyword, "longitude": longitude, "latitude": latitude}
        )
        return self.places

    async def public_transit_route(
        self,
        *,
        origin_longitude,
        origin_latitude,
        destination_longitude,
        destination_latitude,
    ):
        self.route_requests.append((destination_longitude, destination_latitude))
        return self.routes.get((destination_longitude, destination_latitude))

    async def administrative_district(self, *, longitude, latitude):
        self.district_lookup_coordinates.append((longitude, latitude))
        return self.districts.get((longitude, latitude))


def place(name, longitude, latitude):
    return KakaoPlace(
        id=name,
        name=name,
        address=f"{name} 주소",
        longitude=longitude,
        latitude=latitude,
    )


def route(minutes, distance=1_000):
    return KakaoTransitRoute(
        duration_seconds=minutes * 60,
        distance_meters=distance,
        steps=[
            RouteStep(
                instruction="버스로 이동",
                distance_meters=distance,
                duration_seconds=minutes * 60,
                transport_mode="transit",
            )
        ],
    )


def test_client_uses_exact_kakao_authorization_and_cafe_keyword_request():
    captured = []

    async def handler(request):
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "documents": [
                    {
                        "id": "123",
                        "place_name": "테스트 카페",
                        "address_name": "경기 용인시 처인구 모현읍",
                        "road_address_name": "경기 용인시 처인구 외대로 81",
                        "x": "127.2675",
                        "y": "37.3345",
                    }
                ]
            },
        )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = KakaoClient(api_key="test-rest-key", http_client=http_client)
            return await client.search_places(
                keyword="카페", longitude=127.267, latitude=37.334
            )

    result = run(exercise())

    assert len(captured) == 1
    request = captured[0]
    assert request.url.path == "/v2/local/search/keyword.json"
    assert request.headers["Authorization"] == "KakaoAK test-rest-key"
    assert request.url.params["query"] == "카페"
    assert request.url.params["x"] == "127.267"
    assert request.url.params["y"] == "37.334"
    assert result == [
        KakaoPlace(
            id="123",
            name="테스트 카페",
            address="경기 용인시 처인구 외대로 81",
            longitude=127.2675,
            latitude=37.3345,
        )
    ]


def test_reads_only_h_administrative_district_from_coordinate_response():
    captured = []

    async def handler(request):
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "documents": [
                    {
                        "region_type": "B",
                        "code": "1168010100",
                        "region_3depth_name": "신사동",
                    },
                    {
                        "region_type": "H",
                        "code": "1168065000",
                        "region_3depth_name": "신사동",
                    },
                ]
            },
        )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = KakaoClient(api_key="test-rest-key", http_client=http_client)
            return await client.administrative_district(
                longitude=127.1, latitude=37.5
            )

    district = run(exercise())

    assert captured[0].url.path == "/v2/local/geo/coord2regioncode.json"
    assert captured[0].headers["Authorization"] == "KakaoAK test-rest-key"
    assert captured[0].url.params["x"] == "127.1"
    assert captured[0].url.params["y"] == "37.5"
    assert district == KakaoAdministrativeDistrict(
        code="1168065000", name="신사동"
    )


def test_returns_no_administrative_district_when_coordinate_response_has_no_h_record():
    async def handler(request):
        return httpx.Response(
            200,
            json={
                "documents": [
                    {
                        "region_type": "B",
                        "code": "1168010100",
                        "region_3depth_name": "신사동",
                    }
                ]
            },
        )

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = KakaoClient(api_key="test-rest-key", http_client=http_client)
            return await client.administrative_district(
                longitude=127.1, latitude=37.5
            )

    assert run(exercise()) is None


def test_public_transit_client_uses_publictraffic_endpoint_and_provider_values():
    captured = []
    provider_payload = {
        "status": "OK",
        "routes": [
            {
                "properties": {
                    "type": "BUS_AND_SUBWAY",
                    "totalTime": 1_800,
                    "totalDistance": 12_345,
                },
                "steps": [
                    {
                        "properties": {
                            "guidance": "111번 버스 승차",
                            "type": "BUS",
                            "time": 1_500,
                            "distance": 11_500,
                        }
                    },
                    {
                        "properties": {
                            "guidance": "목적지까지 걷기",
                            "type": "WALKING",
                            "time": 300,
                            "distance": 845,
                        }
                    },
                ],
            }
        ]
    }

    async def handler(request):
        captured.append(request)
        return httpx.Response(200, json=provider_payload)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = KakaoClient(api_key="test-rest-key", http_client=http_client)
            return await client.public_transit_route(
                origin_longitude=127.267,
                origin_latitude=37.334,
                destination_longitude=127.300,
                destination_latitude=37.400,
            )

    result = run(exercise())

    assert captured[0].url.path == "/v2/routing/publictraffic"
    assert captured[0].url.host == "dapi.kakao.com"
    assert captured[0].headers["Authorization"] == "KakaoAK test-rest-key"
    assert captured[0].url.params["start_x"] == "127.267"
    assert captured[0].url.params["start_y"] == "37.334"
    assert captured[0].url.params["end_x"] == "127.3"
    assert captured[0].url.params["end_y"] == "37.4"
    assert result == KakaoTransitRoute(
        duration_seconds=1_800,
        distance_meters=12_345,
        steps=[
            RouteStep(
                instruction="111번 버스 승차",
                distance_meters=11_500,
                duration_seconds=1_500,
                transport_mode="transit",
            ),
            RouteStep(
                instruction="목적지까지 걷기",
                distance_meters=845,
                duration_seconds=300,
                transport_mode="walking",
            ),
        ],
    )


def test_outside_korea_coordinates_are_rejected_before_external_call():
    client = StubKakaoClient()
    service = KakaoTransitRecommendationService(client)

    with pytest.raises(ValidationError):
        request = valid_request(
            origin_latitude=37.7749, origin_longitude=-122.4194
        )
        run(service.recommend(request))

    assert client.searches == []
    assert client.route_requests == []


@pytest.mark.parametrize(
    ("name", "latitude", "longitude"),
    [
        ("쓰시마", 34.2038, 129.2908),
        ("후쿠오카", 33.5902, 130.4017),
        ("다롄", 38.6500, 121.6200),
        ("평양", 39.0392, 125.7625),
    ],
)
def test_foreign_coordinates_are_rejected_before_external_call(
    name, latitude, longitude
):
    client = StubKakaoClient()
    service = KakaoTransitRecommendationService(client)

    with pytest.raises(ValidationError):
        request = valid_request(
            origin_name=name,
            origin_latitude=latitude,
            origin_longitude=longitude,
        )
        run(service.recommend(request))

    assert client.searches == []
    assert client.route_requests == []


@pytest.mark.parametrize(
    ("name", "latitude", "longitude"),
    [
        ("개성", 37.9708, 126.5547),
        ("비무장지대 이북", 38.1500, 126.8500),
    ],
)
def test_dprk_coordinates_are_rejected_before_external_call(
    name, latitude, longitude
):
    client = StubKakaoClient()
    service = KakaoTransitRecommendationService(client)

    with pytest.raises(ValidationError):
        request = valid_request(
            origin_name=name,
            origin_latitude=latitude,
            origin_longitude=longitude,
        )
        run(service.recommend(request))

    assert client.searches == []
    assert client.route_requests == []


def test_service_revalidates_coordinates_mutated_after_request_construction():
    client = StubKakaoClient()
    service = KakaoTransitRecommendationService(client)
    request = valid_request()
    request.origin_name = "쓰시마"
    request.origin_latitude = 34.2038
    request.origin_longitude = 129.2908

    with pytest.raises(ValidationError):
        run(service.recommend(request))

    assert client.searches == []
    assert client.route_requests == []


@pytest.mark.parametrize(
    ("name", "latitude", "longitude"),
    [
        ("서울", 37.5665, 126.9780),
        ("파주", 37.7599, 126.7800),
        ("연천", 38.0964, 127.0748),
        ("철원", 38.1467, 127.3134),
        ("고성", 38.3806, 128.4679),
        ("부산", 35.1796, 129.0756),
        ("제주", 33.4996, 126.5312),
        ("백령도", 37.9667, 124.6333),
        ("울릉도", 37.4845, 130.9057),
        ("독도", 37.2429, 131.8648),
    ],
)
def test_authoritative_region_keeps_korean_origins_valid(
    name, latitude, longitude
):
    request = valid_request(
        origin_name=name,
        origin_latitude=latitude,
        origin_longitude=longitude,
    )

    assert request.origin_name == name


def test_service_searches_with_cafe_keyword_from_the_selected_origin():
    client = StubKakaoClient()
    service = KakaoTransitRecommendationService(client)

    run(service.recommend(valid_request()))

    assert client.searches == [
        {"keyword": "카페", "longitude": 127.267, "latitude": 37.334}
    ]


def test_over_limit_and_missing_transit_routes_are_excluded():
    places = [
        place("30분 카페", 127.1, 37.1),
        place("31분 카페", 127.2, 37.2),
        place("경로 없는 카페", 127.3, 37.3),
    ]
    client = StubKakaoClient(
        places,
        routes={
            (127.1, 37.1): route(30),
            (127.2, 37.2): route(31),
            (127.3, 37.3): None,
        },
    )
    service = KakaoTransitRecommendationService(client)

    result = run(service.recommend(valid_request(max_travel_time_minutes=30)))

    assert [item.place_name for item in result.recommendations] == ["30분 카페"]
    recommendation = result.recommendations[0]
    assert recommendation.expected_travel_time_seconds == 1_800
    assert recommendation.distance_meters == 1_000
    assert recommendation.route_steps == route(30).steps
    assert result.provider == "kakao"
    assert result.fixture is False
    assert client.district_lookup_coordinates == []


def test_thirty_minute_recommendations_exclude_routes_shorter_than_twenty_minutes():
    places = [
        place("19분 카페", 127.10, 37.10),
        place("20분 카페", 127.20, 37.20),
        place("30분 카페", 127.30, 37.30),
    ]
    client = StubKakaoClient(
        places,
        routes={
            (127.10, 37.10): route(19),
            (127.20, 37.20): route(20),
            (127.30, 37.30): route(30),
        },
    )
    service = KakaoTransitRecommendationService(client)

    result = run(service.recommend(valid_request(max_travel_time_minutes=30)))

    assert [item.place_name for item in result.recommendations] == [
        "20분 카페",
        "30분 카페",
    ]


def test_expands_place_search_when_nearby_candidates_miss_the_selected_time_window():
    origin = (127.267, 37.334)
    nearby_place = place("5분 카페", 127.268, 37.334)
    target_place = place("25분 카페", 127.320, 37.370)

    class TimeWindowSearchClient(StubKakaoClient):
        async def search_places(self, *, keyword, longitude, latitude):
            self.searches.append(
                {"keyword": keyword, "longitude": longitude, "latitude": latitude}
            )
            return [nearby_place] if (longitude, latitude) == origin else [target_place]

    client = TimeWindowSearchClient(
        routes={
            (nearby_place.longitude, nearby_place.latitude): route(5),
            (target_place.longitude, target_place.latitude): route(25),
        }
    )
    service = KakaoTransitRecommendationService(client)

    result = run(service.recommend(valid_request(max_travel_time_minutes=30)))

    assert [item.place_name for item in result.recommendations] == ["25분 카페"]
    assert client.searches[0] == {
        "keyword": "카페",
        "longitude": 127.267,
        "latitude": 37.334,
    }
    assert len(client.searches) == 9


def test_nearby_walking_route_below_selected_time_window_is_excluded():
    client = StubKakaoClient(
        places=[place("회기역 카페", 127.0577, 37.5904)],
        routes={(127.0577, 37.5904): None},
    )
    service = KakaoTransitRecommendationService(client)

    result = run(
        service.recommend(
            valid_request(
                origin_name="회기역",
                origin_latitude=37.5895,
                origin_longitude=127.0577,
                max_travel_time_minutes=30,
            )
        )
    )

    assert result.result_status == "no_eligible_candidates"
    assert result.eligible_count == 0


def test_district_recommendations_resolve_only_route_eligible_places_and_omit_missing_h():
    places = [
        place("30분 카페", 127.1, 37.1),
        place("H 없는 카페", 127.2, 37.2),
        place("31분 카페", 127.3, 37.3),
        place("경로 없는 카페", 127.4, 37.4),
    ]
    client = StubKakaoClient(
        places,
        routes={
            (127.1, 37.1): route(30),
            (127.2, 37.2): route(29),
            (127.3, 37.3): route(31),
            (127.4, 37.4): None,
        },
        districts={
            (127.1, 37.1): KakaoAdministrativeDistrict(
                code="1168065000", name="신사동"
            ),
            (127.2, 37.2): None,
        },
    )
    service = KakaoTransitRecommendationService(client)

    response = run(service.recommend_districts(valid_request(max_travel_time_minutes=30)))

    assert set(client.district_lookup_coordinates) == {(127.1, 37.1), (127.2, 37.2)}
    assert response.eligible_count == 2
    assert [district.district_name for district in response.districts] == ["신사동"]
    assert [
        recommendation.place_name for recommendation in response.districts[0].places
    ] == ["30분 카페"]


def test_empty_provider_results_do_not_fall_back_to_fixture_candidates():
    client = StubKakaoClient(places=[])
    service = KakaoTransitRecommendationService(client)

    result = run(service.recommend(valid_request()))

    assert result.result_status == "no_eligible_candidates"
    assert result.recommendations == []
    assert result.provider == "kakao"
    assert result.fixture is False
    assert client.route_requests == []


def test_route_concurrency_and_result_count_cannot_exceed_product_caps():
    class CountingClient(StubKakaoClient):
        def __init__(self):
            super().__init__(
                places=[
                    place(f"카페 {index}", 127.0 + index / 100, 37.0)
                    for index in range(6)
                ]
            )
            self.in_flight = 0
            self.peak_in_flight = 0

        async def public_transit_route(self, **coordinates):
            self.in_flight += 1
            self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
            await asyncio.sleep(0.01)
            self.in_flight -= 1
            return route(20)

    client = CountingClient()
    service = KakaoTransitRecommendationService(
        client,
        maximum_concurrent_routes=99,
        maximum_recommendations=99,
    )

    result = run(service.recommend(valid_request()))

    assert client.peak_in_flight == 4
    assert len(result.recommendations) == 5
