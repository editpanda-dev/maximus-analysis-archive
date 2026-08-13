from typing import Any

import httpx

from .live_models import KakaoPlace, KakaoTransitRoute, RouteStep


LOCAL_API_BASE_URL = "https://dapi.kakao.com"
ROUTING_API_BASE_URL = "https://dapi.kakao.com"


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
        response.raise_for_status()

        return [self._parse_place(document) for document in response.json()["documents"]]

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
        response.raise_for_status()
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
                )
            )
        return steps

    @staticmethod
    def _transport_mode(provider_type: str) -> str:
        if provider_type.upper() in {"WALK", "WALKING", "PEDESTRIAN"}:
            return "walking"
        return "transit"
