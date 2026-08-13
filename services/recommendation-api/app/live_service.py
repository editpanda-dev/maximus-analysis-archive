import asyncio
from datetime import datetime, timezone

from .kakao_client import KakaoClient
from .live_models import (
    KakaoPlace,
    LiveRecommendation,
    LiveRecommendationRequest,
    LiveRecommendationResponse,
)


PURPOSE_KEYWORDS = {
    "food": "맛집",
    "cafe": "카페",
    "date": "데이트",
    "shopping": "쇼핑",
    "culture": "문화시설",
    "rest": "휴식",
}
LIMITATIONS = (
    "카카오가 제공한 장소 및 대중교통 경로만 사용합니다. 실시간 도착예정, "
    "혼잡도, 요금, 환승 성공 여부는 보장하지 않습니다."
)


class KakaoTransitRecommendationService:
    def __init__(
        self,
        client: KakaoClient,
        *,
        maximum_concurrent_routes: int = 4,
        maximum_recommendations: int = 5,
    ) -> None:
        self._client = client
        self._maximum_concurrent_routes = min(
            4, max(1, maximum_concurrent_routes)
        )
        self._maximum_recommendations = min(5, max(1, maximum_recommendations))

    async def recommend(
        self, request: LiveRecommendationRequest
    ) -> LiveRecommendationResponse:
        request = LiveRecommendationRequest.model_validate(request.model_dump())
        places = await self._client.search_places(
            keyword=PURPOSE_KEYWORDS[request.purpose],
            longitude=request.origin_longitude,
            latitude=request.origin_latitude,
        )
        semaphore = asyncio.Semaphore(self._maximum_concurrent_routes)

        async def recommendation_for(
            place: KakaoPlace,
        ) -> LiveRecommendation | None:
            async with semaphore:
                route = await self._client.public_transit_route(
                    origin_longitude=request.origin_longitude,
                    origin_latitude=request.origin_latitude,
                    destination_longitude=place.longitude,
                    destination_latitude=place.latitude,
                )
            if route is None:
                return None
            if route.duration_seconds > request.max_travel_time_minutes * 60:
                return None
            return LiveRecommendation(
                place_name=place.name,
                address=place.address,
                destination_latitude=place.latitude,
                destination_longitude=place.longitude,
                expected_travel_time_seconds=route.duration_seconds,
                distance_meters=route.distance_meters,
                route_steps=route.steps,
            )

        routed = await asyncio.gather(
            *(recommendation_for(place) for place in places)
        )
        eligible = [recommendation for recommendation in routed if recommendation]
        eligible.sort(
            key=lambda recommendation: (
                recommendation.expected_travel_time_seconds,
                recommendation.distance_meters,
                recommendation.place_name,
            )
        )
        recommendations = eligible[: self._maximum_recommendations]

        return LiveRecommendationResponse(
            result_status="ok" if recommendations else "no_eligible_candidates",
            queried_at=datetime.now(timezone.utc),
            eligible_count=len(eligible),
            recommendations=recommendations,
            limitations=LIMITATIONS,
        )
