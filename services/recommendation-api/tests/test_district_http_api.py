import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.kakao_client import KakaoProviderError
from app.live_models import LiveRecommendationResponse
import app.main as main


app = main.app


@asynccontextmanager
async def live_service_context(service):
    yield service


def valid_payload(**overrides):
    payload = {
        "origin_name": "한국외국어대학교 글로벌캠퍼스",
        "origin_latitude": 37.334,
        "origin_longitude": 127.267,
        "purpose": "cafe",
        "max_travel_time_minutes": 30,
    }
    payload.update(overrides)
    return payload


class StubDistrictRecommendationService:
    def __init__(self, response=None):
        self.response = response or {
            "result_status": "ok",
            "provider": "kakao",
            "queried_at": datetime.now(timezone.utc),
            "eligible_count": 2,
            "districts": [
                {
                    "district_name": "모현읍",
                    "fastest_travel_time_seconds": 1_200,
                    "place_count": 2,
                    "places": [
                        {
                            "place_name": "테스트 카페",
                            "address": "경기 용인시 처인구 모현읍 외대로 42-1",
                            "destination_latitude": 37.3345,
                            "destination_longitude": 127.2675,
                            "expected_travel_time_seconds": 1_200,
                            "distance_meters": 1_000,
                            "route_steps": [],
                        }
                    ],
                }
            ],
            "fixture": False,
            "limitations": "Provider-supplied routes only.",
        }

    async def recommend_districts(self, request):
        return self.response


class FailingDistrictRecommendationService:
    def __init__(self, status_code):
        self.status_code = status_code

    async def recommend_districts(self, request):
        raise KakaoProviderError(self.status_code)


class DirectOnlyRecommendationService:
    def __init__(self):
        self.recommend_requests = []

    async def recommend(self, request):
        self.recommend_requests.append(request)
        return LiveRecommendationResponse(
            result_status="ok",
            queried_at=datetime.now(timezone.utc),
            eligible_count=1,
            recommendations=[],
            limitations="Provider-supplied routes only.",
        )

    async def recommend_districts(self, request):
        raise AssertionError("direct-place endpoint must not request districts")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def service_stub(monkeypatch):
    service = StubDistrictRecommendationService()
    monkeypatch.setattr(
        main,
        "get_live_recommendation_service",
        lambda: live_service_context(service),
    )
    return service


def test_live_district_endpoint_returns_grouped_kakao_only_response(
    client, service_stub
):
    response = client.post("/v1/live-district-recommendations", json=valid_payload())

    assert response.status_code == 200
    assert response.json()["provider"] == "kakao"
    assert response.json()["fixture"] is False
    assert response.json()["districts"][0]["district_name"] == "모현읍"


def test_live_district_endpoint_keeps_same_named_districts_with_distinct_codes_as_cards(
    client, service_stub
):
    service_stub.response["districts"] = [
        {
            "district_name": "신사동",
            "fastest_travel_time_seconds": 1_200,
            "place_count": 1,
            "places": [
                {
                    "place_name": "강남 카페",
                    "address": "서울 강남구 신사동",
                    "destination_latitude": 37.517,
                    "destination_longitude": 127.022,
                    "expected_travel_time_seconds": 1_200,
                    "distance_meters": 900,
                    "route_steps": [],
                }
            ],
        },
        {
            "district_name": "신사동",
            "fastest_travel_time_seconds": 1_300,
            "place_count": 1,
            "places": [
                {
                    "place_name": "관악 카페",
                    "address": "서울 관악구 신사동",
                    "destination_latitude": 37.487,
                    "destination_longitude": 126.927,
                    "expected_travel_time_seconds": 1_300,
                    "distance_meters": 1_000,
                    "route_steps": [],
                }
            ],
        },
    ]

    response = client.post("/v1/live-district-recommendations", json=valid_payload())

    assert response.status_code == 200
    assert [item["district_name"] for item in response.json()["districts"]] == [
        "신사동",
        "신사동",
    ]
    assert [item["place_count"] for item in response.json()["districts"]] == [1, 1]


def test_live_recommendations_uses_direct_service_path_without_district_resolution(
    client, monkeypatch
):
    service = DirectOnlyRecommendationService()
    monkeypatch.setattr(
        main,
        "get_live_recommendation_service",
        lambda: live_service_context(service),
    )

    response = client.post("/v1/live-recommendations", json=valid_payload())

    assert response.status_code == 200
    assert len(service.recommend_requests) == 1


def test_live_district_endpoint_reports_empty_candidates(client, service_stub):
    service_stub.response = {
        "result_status": "no_eligible_candidates",
        "provider": "kakao",
        "queried_at": datetime.now(timezone.utc),
        "eligible_count": 0,
        "districts": [],
        "fixture": False,
        "limitations": "Provider-supplied routes only.",
    }

    response = client.post("/v1/live-district-recommendations", json=valid_payload())

    assert response.status_code == 200
    assert response.json()["result_status"] == "no_eligible_candidates"
    assert response.json()["districts"] == []


def test_foreign_origin_is_422_even_without_a_kakao_key(client, monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    response = client.post(
        "/v1/live-district-recommendations",
        json=valid_payload(origin_latitude=37.7749, origin_longitude=-122.4194),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(("provider_status", "expected_status"), [(429, 429), (502, 503)])
def test_live_district_endpoint_maps_provider_errors(
    client, monkeypatch, provider_status, expected_status
):
    monkeypatch.setattr(
        main,
        "get_live_recommendation_service",
        lambda: live_service_context(
            FailingDistrictRecommendationService(provider_status)
        ),
    )

    response = client.post("/v1/live-district-recommendations", json=valid_payload())

    assert response.status_code == expected_status
    assert response.json()["detail"] == "Live recommendations are temporarily unavailable."
