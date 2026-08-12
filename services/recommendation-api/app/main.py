from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

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
