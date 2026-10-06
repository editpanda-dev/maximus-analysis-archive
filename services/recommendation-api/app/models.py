from typing import Literal

from pydantic import BaseModel, Field


TransportMode = Literal["public_transit"]
MaxTravelTime = Literal[20, 30, 40, 60]
TimeSlot = Literal["morning", "lunch", "afternoon", "evening", "night"]
Purpose = Literal["food", "cafe", "date", "shopping", "culture", "rest", "study"]
RouteStatus = Literal["available_verified", "no_route", "unverified"]
CostStatus = Literal["available", "unavailable"]


class RecommendationRequest(BaseModel):
    origin: str = Field(min_length=1)
    transport_mode: TransportMode
    max_travel_time_minutes: MaxTravelTime
    time_slot: TimeSlot
    purpose: Purpose


class FixtureCandidate(BaseModel):
    id: str
    name: str
    district: str
    journey_time_minutes: int | None = Field(default=None, ge=0)
    route_status: RouteStatus
    cost_status: CostStatus
    cost_won: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    vintage: str = "F0-fixture-v1"


class Recommendation(BaseModel):
    id: str
    name: str
    district: str
    journey_time_minutes: int
    route_status: Literal["available_verified"]
    cost_status: CostStatus
    cost_won: int | None = Field(default=None, ge=0)
    tags: list[str] = Field(default_factory=list)
    reason: str
    signal: str
    method: str
    vintage: str


class RecommendationResponse(BaseModel):
    result_status: Literal["ok", "no_eligible_candidates"]
    eligible_count: int = Field(ge=0)
    recommendations: list[Recommendation] = Field(default_factory=list)
    ranking_basis: Literal["F0-public-rule"]
    fixture: Literal[True]
    limitations: str = Field(min_length=1)
