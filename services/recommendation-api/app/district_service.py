import re

from .live_models import DistrictRecommendation, LiveRecommendation


DISTRICT_SUFFIXES = ("읍", "면", "동")
DISTRICT_TOKEN_PATTERN = re.compile(
    r"^[가-힣]+(?:\d+(?:\.\d+)*)?[가-힣]*[읍면동]$"
)
LOCALITY_TOKEN_PATTERN = re.compile(r"^[가-힣]+[시군구]$")


def extract_administrative_district(address: str) -> str | None:
    tokens = address.split()
    for index, token in enumerate(tokens):
        if (
            index > 0
            and LOCALITY_TOKEN_PATTERN.fullmatch(tokens[index - 1])
            and token.endswith(DISTRICT_SUFFIXES)
            and DISTRICT_TOKEN_PATTERN.fullmatch(token)
        ):
            return token
    return None


def build_district_recommendations(
    places: list[LiveRecommendation], maximum_districts: int = 5
) -> list[DistrictRecommendation]:
    places_by_district: dict[str, list[LiveRecommendation]] = {}
    for place in places:
        district_name = extract_administrative_district(place.address)
        if district_name:
            places_by_district.setdefault(district_name, []).append(place)

    districts = []
    for district_name, district_places in places_by_district.items():
        sorted_places = sorted(
            district_places,
            key=lambda place: (
                place.expected_travel_time_seconds,
                place.distance_meters,
                place.place_name,
            ),
        )
        fastest_place = sorted_places[0]
        districts.append(
            DistrictRecommendation(
                district_name=district_name,
                fastest_travel_time_seconds=fastest_place.expected_travel_time_seconds,
                place_count=len(sorted_places),
                places=sorted_places,
            )
        )

    districts.sort(
        key=lambda district: (
            district.fastest_travel_time_seconds,
            -district.place_count,
            district.places[0].distance_meters,
            district.district_name,
        )
    )
    return districts[: min(5, max(1, maximum_districts))]
