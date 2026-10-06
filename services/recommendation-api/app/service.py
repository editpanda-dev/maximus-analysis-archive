from .models import Recommendation, RecommendationRequest, RecommendationResponse
from .repository import get_fixture_candidates

RANKING_BASIS = "F0-public-rule"
LIMITATIONS = "데모 fixture이며 실제 관측값이 아닙니다. 실시간 대중교통 정보가 아니며, 개인화 추천이나 인과관계를 보장하지 않습니다."
MAX_RECOMMENDATIONS = 5
PURPOSE_LABELS = {"food": "식사", "cafe": "카페", "date": "데이트", "shopping": "쇼핑", "culture": "문화", "rest": "휴식", "study": "공부"}
PURPOSE_RANKINGS = {
    "food": ("food_mangwon", "cafe_bukchon", "date_seongsu", "culture_jongno", "rest_yongsan", "shopping_hongdae"),
    "cafe": ("cafe_bukchon", "rest_yongsan", "culture_jongno", "food_mangwon", "date_seongsu", "shopping_hongdae"),
    "date": ("date_seongsu", "cafe_bukchon", "rest_yongsan", "food_mangwon", "culture_jongno", "shopping_hongdae"),
    "shopping": ("shopping_hongdae", "cafe_bukchon", "food_mangwon", "date_seongsu", "culture_jongno", "rest_yongsan"),
    "culture": ("culture_jongno", "rest_yongsan", "cafe_bukchon", "date_seongsu", "food_mangwon", "shopping_hongdae"),
    "rest": ("rest_yongsan", "cafe_bukchon", "culture_jongno", "date_seongsu", "shopping_hongdae", "food_mangwon"),
    "study": ("cafe_bukchon", "rest_yongsan", "culture_jongno", "food_mangwon", "date_seongsu", "shopping_hongdae"),
}


def _eligible_candidates(request: RecommendationRequest):
    return tuple(candidate for candidate in get_fixture_candidates() if candidate.route_status == "available_verified" and candidate.journey_time_minutes is not None and candidate.journey_time_minutes <= request.max_travel_time_minutes)


def _rank_candidates(request: RecommendationRequest):
    priority = {candidate_id: position for position, candidate_id in enumerate(PURPOSE_RANKINGS[request.purpose])}
    return sorted(_eligible_candidates(request), key=lambda candidate: (priority.get(candidate.id, len(priority)), candidate.journey_time_minutes, candidate.id))


def recommend(request: RecommendationRequest) -> RecommendationResponse:
    """Return deterministic recommendations from the F0 fixture only."""
    eligible = _eligible_candidates(request)
    label = PURPOSE_LABELS[request.purpose]
    recommendations = [Recommendation(id=candidate.id, name=candidate.name, district=candidate.district, journey_time_minutes=candidate.journey_time_minutes, route_status="available_verified", cost_status=candidate.cost_status, cost_won=candidate.cost_won if candidate.cost_status == "available" else None, tags=list(candidate.tags), reason=f"{label} 목적의 fixture 프로필에서 {candidate.name}을(를) 우선한 F0 규칙입니다.", signal=f"fixture_{request.purpose}_profile", method="fixture_rule_v1", vintage=candidate.vintage) for candidate in _rank_candidates(request)[:MAX_RECOMMENDATIONS]]
    return RecommendationResponse(result_status="ok" if recommendations else "no_eligible_candidates", eligible_count=len(eligible), recommendations=recommendations, ranking_basis=RANKING_BASIS, fixture=True, limitations=LIMITATIONS)
