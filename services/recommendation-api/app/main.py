import os
from collections.abc import AsyncIterator
from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .kakao_client import KakaoClient, KakaoProviderError
from .live_models import (
    LiveDistrictRecommendationResponse,
    LiveRecommendationRequest,
    LiveRecommendationResponse,
)
from .live_service import KakaoTransitRecommendationService
from .models import RecommendationRequest, RecommendationResponse
from .service import recommend


class HealthResponse(BaseModel):
    status: Literal["ok"]
    fixture: Literal[True]


app = FastAPI(title="어디가지 Recommendation API")


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok", fixture=True)


@app.post("/v1/recommendations", response_model=RecommendationResponse)
def recommendations(request: RecommendationRequest) -> RecommendationResponse:
    return recommend(request)


@asynccontextmanager
async def get_live_recommendation_service() -> AsyncIterator[
    KakaoTransitRecommendationService, None
]:
    api_key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Live recommendations are not configured.",
        )

    async with httpx.AsyncClient(timeout=10.0) as http_client:
        yield KakaoTransitRecommendationService(
            KakaoClient(api_key=api_key, http_client=http_client)
        )


@app.post(
    "/v1/live-recommendations", response_model=LiveRecommendationResponse
)
async def live_recommendations(
    request: LiveRecommendationRequest,
) -> LiveRecommendationResponse:
    try:
        async with get_live_recommendation_service() as service:
            return await service.recommend(request)
    except KakaoProviderError as error:
        if error.status_code == 429:
            status_code = 429
        elif 500 <= error.status_code <= 599:
            status_code = 503
        else:
            status_code = 502
        raise HTTPException(
            status_code=status_code,
            detail="Live recommendations are temporarily unavailable.",
        ) from error


@app.post(
    "/v1/live-district-recommendations",
    response_model=LiveDistrictRecommendationResponse,
)
async def live_district_recommendations(
    request: LiveRecommendationRequest,
) -> LiveDistrictRecommendationResponse:
    try:
        async with get_live_recommendation_service() as service:
            return await service.recommend_districts(request)
    except KakaoProviderError as error:
        if error.status_code == 429:
            status_code = 429
        elif 500 <= error.status_code <= 599:
            status_code = 503
        else:
            status_code = 502
        raise HTTPException(
            status_code=status_code,
            detail="Live recommendations are temporarily unavailable.",
        ) from error
