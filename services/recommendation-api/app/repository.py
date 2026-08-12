from .models import FixtureCandidate


FIXTURE_CANDIDATES: tuple[FixtureCandidate, ...] = (
    FixtureCandidate(id="food_mangwon", name="망원 식사 골목", district="마포구", journey_time_minutes=30, route_status="available_verified", cost_status="available", cost_won=12000, tags=["식사", "선택지 다양"]),
    FixtureCandidate(id="cafe_bukchon", name="북촌 커피 마당", district="종로구", journey_time_minutes=20, route_status="available_verified", cost_status="unavailable", cost_won=None, tags=["카페", "조용함"]),
    FixtureCandidate(id="date_seongsu", name="성수 데이트 라운지", district="성동구", journey_time_minutes=25, route_status="available_verified", cost_status="available", cost_won=18000, tags=["데이트", "대화"]),
    FixtureCandidate(id="shopping_hongdae", name="홍대 취향 상점길", district="마포구", journey_time_minutes=18, route_status="available_verified", cost_status="unavailable", cost_won=None, tags=["쇼핑", "개성 있는 상점"]),
    FixtureCandidate(id="culture_jongno", name="종로 문화 산책관", district="종로구", journey_time_minutes=28, route_status="available_verified", cost_status="available", cost_won=9000, tags=["문화", "전시"]),
    FixtureCandidate(id="rest_yongsan", name="용산 느린 쉼터", district="용산구", journey_time_minutes=22, route_status="available_verified", cost_status="unavailable", cost_won=None, tags=["휴식", "산책"]),
    FixtureCandidate(id="over_limit_haneul", name="하늘공원 바람길", district="마포구", journey_time_minutes=35, route_status="available_verified", cost_status="available", cost_won=5000, tags=["산책", "전망"]),
    FixtureCandidate(id="no_route_namsan", name="남산 전망 쉼터", district="중구", journey_time_minutes=24, route_status="no_route", cost_status="unavailable", cost_won=None, tags=["휴식", "전망"]),
    FixtureCandidate(id="unverified_itaewon", name="이태원 취향 거리", district="용산구", journey_time_minutes=26, route_status="unverified", cost_status="unavailable", cost_won=None, tags=["문화", "취향"]),
    FixtureCandidate(id="missing_time_seochon", name="서촌 골목 쉼표", district="종로구", journey_time_minutes=None, route_status="available_verified", cost_status="unavailable", cost_won=None, tags=["휴식", "골목"]),
)


def get_fixture_candidates() -> tuple[FixtureCandidate, ...]:
    """Return the static F0 candidate set; no network or persistence is used."""
    return FIXTURE_CANDIDATES
