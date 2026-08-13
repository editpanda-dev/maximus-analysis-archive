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


class StubLiveRecommendationService:
    async def recommend(self, request):
        return LiveRecommendationResponse(
            result_status="ok",
            queried_at=datetime.now(timezone.utc),
            eligible_count=1,
            recommendations=[],
            limitations="Provider-supplied routes only.",
        )


class FailingLiveRecommendationService:
    def __init__(self, status_code):
        self.status_code = status_code

    async def recommend(self, request):
        raise KakaoProviderError(self.status_code)


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


def test_live_recommendations_returns_live_response_from_injected_service(
    monkeypatch,
):
    monkeypatch.setattr(
        main,
        "get_live_recommendation_service",
        lambda: live_service_context(StubLiveRecommendationService()),
    )
    response = TestClient(app).post(
        "/v1/live-recommendations", json=valid_payload()
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "kakao"
    assert response.json()["fixture"] is False


@pytest.mark.parametrize("api_key", [None, "   "])
def test_live_recommendations_validate_foreign_origins_before_configuration(
    monkeypatch, api_key
):
    if api_key is None:
        monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    else:
        monkeypatch.setenv("KAKAO_REST_API_KEY", api_key)

    response = TestClient(app).post(
        "/v1/live-recommendations",
        json=valid_payload(origin_latitude=37.7749, origin_longitude=-122.4194),
    )

    assert response.status_code == 422


def test_live_recommendations_missing_key_returns_safe_configuration_error(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    response = TestClient(app).post("/v1/live-recommendations", json=valid_payload())

    assert response.status_code == 503
    assert "KAKAO_REST_API_KEY" not in response.text
    assert "key" not in response.json()["detail"].lower()


def test_live_recommendations_maps_provider_rate_limit_to_safe_error(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_live_recommendation_service",
        lambda: live_service_context(FailingLiveRecommendationService(429)),
    )
    response = TestClient(app).post(
        "/v1/live-recommendations", json=valid_payload()
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Live recommendations are temporarily unavailable."


def test_live_recommendations_maps_provider_server_errors_to_safe_error(
    monkeypatch,
):
    monkeypatch.setattr(
        main,
        "get_live_recommendation_service",
        lambda: live_service_context(FailingLiveRecommendationService(502)),
    )
    response = TestClient(app).post(
        "/v1/live-recommendations", json=valid_payload()
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Live recommendations are temporarily unavailable."
