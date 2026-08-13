from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .korea_region import is_south_korea_coordinate


Purpose = Literal["food", "cafe", "date", "shopping", "culture", "rest"]
MaxTravelTime = Literal[20, 30, 40, 60]
TransportMode = Literal["walking", "transit"]


class LiveRecommendationRequest(BaseModel):
    origin_name: str = Field(min_length=1)
    origin_latitude: float = Field(ge=33.0, le=38.7)
    origin_longitude: float = Field(ge=124.0, le=132.0)
    purpose: Purpose
    max_travel_time_minutes: MaxTravelTime

    @model_validator(mode="after")
    def validate_origin_is_in_south_korea(self):
        if not is_south_korea_coordinate(
            latitude=self.origin_latitude,
            longitude=self.origin_longitude,
        ):
            raise ValueError(
                "origin coordinates must be within supported South Korea regions"
            )
        return self


class KakaoPlace(BaseModel):
    id: str
    name: str = Field(min_length=1)
    address: str
    longitude: float
    latitude: float


class KakaoAdministrativeDistrict(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


class RouteStep(BaseModel):
    instruction: str = Field(min_length=1)
    distance_meters: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    transport_mode: TransportMode


class KakaoTransitRoute(BaseModel):
    duration_seconds: int = Field(ge=0)
    distance_meters: int = Field(ge=0)
    steps: list[RouteStep] = Field(default_factory=list)


class LiveRecommendation(BaseModel):
    place_name: str
    address: str
    destination_latitude: float
    destination_longitude: float
    expected_travel_time_seconds: int = Field(ge=0)
    distance_meters: int = Field(ge=0)
    route_steps: list[RouteStep] = Field(default_factory=list)


class DistrictCandidate(BaseModel):
    district_code: str = Field(min_length=1)
    district_name: str = Field(min_length=1)
    place: LiveRecommendation


class DistrictRecommendation(BaseModel):
    district_name: str = Field(min_length=1)
    fastest_travel_time_seconds: int = Field(ge=0)
    place_count: int = Field(ge=1)
    places: list[LiveRecommendation] = Field(min_length=1)


class LiveRecommendationResponse(BaseModel):
    result_status: Literal["ok", "no_eligible_candidates"]
    provider: Literal["kakao"] = "kakao"
    queried_at: datetime
    eligible_count: int = Field(ge=0)
    recommendations: list[LiveRecommendation] = Field(default_factory=list)
    fixture: Literal[False] = False
    limitations: str = Field(min_length=1)


class LiveDistrictRecommendationResponse(BaseModel):
    result_status: Literal["ok", "no_eligible_candidates"]
    provider: Literal["kakao"] = "kakao"
    queried_at: datetime
    eligible_count: int = Field(ge=0)
    districts: list[DistrictRecommendation] = Field(default_factory=list)
    fixture: Literal[False] = False
    limitations: str = Field(min_length=1)
