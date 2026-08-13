from .live_models import DistrictCandidate, DistrictRecommendation


def build_district_recommendations(
    candidates: list[DistrictCandidate], maximum_districts: int = 5
) -> list[DistrictRecommendation]:
    candidates_by_district: dict[str, list[DistrictCandidate]] = {}
    for candidate in candidates:
        candidates_by_district.setdefault(candidate.district_code, []).append(candidate)

    districts = []
    for district_candidates in candidates_by_district.values():
        sorted_places = sorted(
            (candidate.place for candidate in district_candidates),
            key=lambda place: (
                place.expected_travel_time_seconds,
                place.distance_meters,
                place.place_name,
            ),
        )
        fastest_place = sorted_places[0]
        districts.append(
            DistrictRecommendation(
                district_name=district_candidates[0].district_name,
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
