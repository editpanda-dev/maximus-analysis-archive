import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.models import RecommendationRequest
from app.service import recommend


def make_request(**overrides):
    data = {"origin": "회기역", "transport_mode": "public_transit", "max_travel_time_minutes": 30, "time_slot": "evening", "purpose": "food"}
    data.update(overrides)
    return RecommendationRequest(**data)


class RecommendationTests(unittest.TestCase):
    def test_food_and_cafe_change_first_destination(self):
        food, cafe = recommend(make_request(purpose="food")), recommend(make_request(purpose="cafe"))
        self.assertNotEqual(food.recommendations[0].id, cafe.recommendations[0].id)
        self.assertNotEqual(food.recommendations[0].reason, cafe.recommendations[0].reason)

    def test_hard_filter_includes_boundary_and_excludes_invalid_candidates(self):
        result = recommend(make_request(max_travel_time_minutes=30))
        ids = {item.id for item in result.recommendations}
        self.assertEqual(result.eligible_count, 6)
        self.assertIn("food_mangwon", ids)
        self.assertNotIn("over_limit_haneul", ids)
        self.assertNotIn("no_route_namsan", ids)
        self.assertNotIn("unverified_itaewon", ids)
        self.assertNotIn("missing_time_seochon", ids)
        self.assertTrue(all(item.route_status == "available_verified" and item.journey_time_minutes <= 30 for item in result.recommendations))

    def test_result_is_capped_at_five(self):
        self.assertEqual(len(recommend(make_request()).recommendations), 5)

    def test_metadata_is_transparent_for_all_purposes(self):
        for purpose in ("food", "cafe", "date", "shopping", "culture", "rest"):
            result = recommend(make_request(purpose=purpose))
            self.assertTrue(result.fixture)
            self.assertEqual(result.ranking_basis, "F0-public-rule")
            for phrase in ("데모 fixture", "실시간 대중교통", "개인화", "인과관계"):
                self.assertIn(phrase, result.limitations)

    def test_each_purpose_is_deterministic_and_distinct(self):
        purposes = ("food", "cafe", "date", "shopping", "culture", "rest")
        first_ids = [recommend(make_request(purpose=purpose)).recommendations[0].id for purpose in purposes]
        self.assertEqual(len(set(first_ids)), len(purposes))
        self.assertEqual(first_ids, [recommend(make_request(purpose=purpose)).recommendations[0].id for purpose in purposes])

    def test_unavailable_cost_is_none_never_zero(self):
        results = recommend(make_request(purpose="cafe")).recommendations
        self.assertTrue(any(item.cost_status == "unavailable" for item in results))
        self.assertTrue(all(item.cost_won is None for item in results if item.cost_status == "unavailable"))
        self.assertTrue(all(item.cost_won != 0 for item in results))

    def test_unsupported_mode_and_purpose_are_rejected(self):
        with self.assertRaises(ValidationError): make_request(transport_mode="walking")
        with self.assertRaises(ValidationError): make_request(purpose="unknown")

    def test_supported_time_limits_and_slots_are_enforced(self):
        with self.assertRaises(ValidationError): make_request(max_travel_time_minutes=25)
        with self.assertRaises(ValidationError): make_request(time_slot="midnight")


if __name__ == "__main__":
    unittest.main()
