from typing import Any

import httpx

from .live_models import (
    KakaoAdministrativeDistrict,
    KakaoPlace,
    KakaoTransitRoute,
    RouteCoordinate,
    RouteStep,
)


LOCAL_API_BASE_URL = "https://dapi.kakao.com"
ROUTING_API_BASE_URL = "https://dapi.kakao.com"


class KakaoProviderError(RuntimeError):
    """Safe provider failure information for the HTTP boundary."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Kakao provider returned HTTP {status_code}")


class KakaoClient:
    def __init__(
        self,
        *,
        api_key: str,
        http_client: httpx.AsyncClient,
        local_api_base_url: str = LOCAL_API_BASE_URL,
        routing_api_base_url: str = ROUTING_API_BASE_URL,
    ) -> None:
        self._http_client = http_client
        self._headers = {"Authorization": f"KakaoAK {api_key}"}
        self._local_api_base_url = local_api_base_url.rstrip("/")
        self._routing_api_base_url = routing_api_base_url.rstrip("/")

    async def search_places(
        self, *, keyword: str, longitude: float, latitude: float
    ) -> list[KakaoPlace]:
        response = await self._http_client.get(
            f"{self._local_api_base_url}/v2/local/search/keyword.json",
            headers=self._headers,
            params={
                "query": keyword,
                "x": longitude,
                "y": latitude,
                "radius": 10_000,
                "sort": "distance",
                "size": 15,
            },
        )
        self._raise_for_provider_error(response)

        return [self._parse_place(document) for document in response.json()["documents"]]

    async def administrative_district(
        self, *, longitude: float, latitude: float
    ) -> KakaoAdministrativeDistrict | None:
        response = await self._http_client.get(
            f"{self._local_api_base_url}/v2/local/geo/coord2regioncode.json",
            headers=self._headers,
            params={"x": longitude, "y": latitude},
        )
        self._raise_for_provider_error(response)
        record = next(
            (
                item
                for item in response.json()["documents"]
                if item.get("region_type") == "H"
            ),
            None,
        )
        if record is None:
            return None
        return KakaoAdministrativeDistrict(
            code=str(record["code"]),
            name=str(record["region_3depth_name"]),
        )

    async def public_transit_route(
        self,
        *,
        origin_longitude: float,
        origin_latitude: float,
        destination_longitude: float,
        destination_latitude: float,
    ) -> KakaoTransitRoute | None:
        response = await self._http_client.get(
            f"{self._routing_api_base_url}/v2/routing/publictraffic",
            headers=self._headers,
            params={
                "start_x": origin_longitude,
                "start_y": origin_latitude,
                "end_x": destination_longitude,
                "end_y": destination_latitude,
            },
        )
        self._raise_for_provider_error(response)
        payload = response.json()
        if payload.get("status") != "OK":
            return None

        routes = payload.get("routes", [])
        successful_routes = [
            route
            for route in routes
            if isinstance(route.get("properties"), dict)
        ]
        if not successful_routes:
            return None

        fastest_route = min(
            successful_routes,
            key=lambda route: int(route["properties"]["totalTime"]),
        )
        properties = fastest_route["properties"]
        return KakaoTransitRoute(
            duration_seconds=int(properties["totalTime"]),
            distance_meters=int(properties["totalDistance"]),
            steps=self._parse_steps(fastest_route),
        )

    @staticmethod
    def _raise_for_provider_error(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise KakaoProviderError(error.response.status_code) from error

    @staticmethod
    def _parse_place(document: dict[str, Any]) -> KakaoPlace:
        return KakaoPlace(
            id=str(document["id"]),
            name=document["place_name"],
            address=document.get("road_address_name")
            or document.get("address_name", ""),
            longitude=float(document["x"]),
            latitude=float(document["y"]),
        )

    @classmethod
    def _parse_steps(cls, route: dict[str, Any]) -> list[RouteStep]:
        steps = []
        for provider_step in route.get("steps", []):
            properties = provider_step.get("properties", {})
            instruction = properties.get("guidance")
            if not instruction:
                continue
            steps.append(
                RouteStep(
                    instruction=str(instruction),
                    distance_meters=int(properties["distance"]),
                    duration_seconds=int(properties["time"]),
                    transport_mode=cls._transport_mode(properties.get("type", "")),
                    path_coordinates=cls._parse_path_coordinates(provider_step),
                )
            )
        return steps

    @staticmethod
    def _parse_path_coordinates(provider_step: dict[str, Any]) -> list[RouteCoordinate]:
        path = provider_step.get("path")
        points = path.get("points") if isinstance(path, dict) else None
        if not isinstance(points, list):
            return []

        coordinates = []
        for point in points:
            if not isinstance(point, list) or len(point) < 2:
                continue
            try:
                longitude, latitude = float(point[0]), float(point[1])
            except (TypeError, ValueError):
                continue
            if -180 <= longitude <= 180 and -90 <= latitude <= 90:
                coordinates.append(
                    RouteCoordinate(latitude=latitude, longitude=longitude)
                )
        return coordinates

    @staticmethod
    def _transport_mode(provider_type: str) -> str:
        if provider_type.upper() in {"WALK", "WALKING", "PEDESTRIAN"}:
            return "walking"
        return "transit"
