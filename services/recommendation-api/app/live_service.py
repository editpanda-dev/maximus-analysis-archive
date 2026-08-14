import asyncio
import math
from datetime import datetime, timezone

from .kakao_client import KakaoClient
from .district_service import build_district_recommendations
from .live_models import (
    DistrictCandidate,
    KakaoPlace,
    KakaoTransitRoute,
    LiveDistrictRecommendationResponse,
    LiveRecommendation,
    LiveRecommendationRequest,
    LiveRecommendationResponse,
    RouteStep,
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
    "카카오 대중교통 경로를 우선 사용합니다. 카카오가 경로를 제공하지 않는 가까운 장소는 "
    "직선 거리 기반 도보 예상으로 표시합니다. 실시간 도착예정, 혼잡도, 요금, "
    "환승 성공 여부는 보장하지 않습니다."
)
WALKING_METERS_PER_MINUTE = 80
EARTH_RADIUS_METERS = 6_371_000


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
        eligible = await self._eligible_recommendations(request)
        recommendations = eligible[: self._maximum_recommendations]

        return LiveRecommendationResponse(
            result_status="ok" if recommendations else "no_eligible_candidates",
            queried_at=datetime.now(timezone.utc),
            eligible_count=len(eligible),
            recommendations=recommendations,
            limitations=LIMITATIONS,
        )

    async def recommend_districts(
        self, request: LiveRecommendationRequest
    ) -> LiveDistrictRecommendationResponse:
        eligible = await self._eligible_recommendations(request)
        candidates = await self._district_candidates(eligible)
        districts = build_district_recommendations(candidates)

        return LiveDistrictRecommendationResponse(
            result_status="ok" if districts else "no_eligible_candidates",
            queried_at=datetime.now(timezone.utc),
            eligible_count=len(eligible),
            districts=districts,
            limitations=LIMITATIONS,
        )

    async def _eligible_recommendations(
        self, request: LiveRecommendationRequest
    ) -> list[LiveRecommendation]:
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
                route = self._nearby_walking_route(request=request, place=place)
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
        return eligible

    @staticmethod
    def _nearby_walking_route(
        *, request: LiveRecommendationRequest, place: KakaoPlace
    ) -> KakaoTransitRoute | None:
        latitude_delta = math.radians(place.latitude - request.origin_latitude)
        longitude_delta = math.radians(place.longitude - request.origin_longitude)
        origin_latitude = math.radians(request.origin_latitude)
        destination_latitude = math.radians(place.latitude)
        half_chord = (
            math.sin(latitude_delta / 2) ** 2
            + math.cos(origin_latitude)
            * math.cos(destination_latitude)
            * math.sin(longitude_delta / 2) ** 2
        )
        distance_meters = round(
            EARTH_RADIUS_METERS * 2 * math.atan2(math.sqrt(half_chord), math.sqrt(1 - half_chord))
        )
        duration_minutes = max(1, math.ceil(distance_meters / WALKING_METERS_PER_MINUTE))
        if duration_minutes > request.max_travel_time_minutes:
            return None

        duration_seconds = duration_minutes * 60
        return KakaoTransitRoute(
            duration_seconds=duration_seconds,
            distance_meters=distance_meters,
            steps=[
                RouteStep(
                    instruction=f"도보 약 {duration_minutes}분",
                    distance_meters=distance_meters,
                    duration_seconds=duration_seconds,
                    transport_mode="walking",
                )
            ],
        )

    async def _district_candidates(
        self, recommendations: list[LiveRecommendation]
    ) -> list[DistrictCandidate]:
        semaphore = asyncio.Semaphore(self._maximum_concurrent_routes)

        async def candidate_for(
            recommendation: LiveRecommendation,
        ) -> DistrictCandidate | None:
            async with semaphore:
                district = await self._client.administrative_district(
                    longitude=recommendation.destination_longitude,
                    latitude=recommendation.destination_latitude,
                )
            if district is None:
                return None
            return DistrictCandidate(
                district_code=district.code,
                district_name=district.name,
                place=recommendation,
            )

        resolved = await asyncio.gather(
            *(candidate_for(recommendation) for recommendation in recommendations)
        )
        return [candidate for candidate in resolved if candidate]
