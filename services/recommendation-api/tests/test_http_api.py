import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.main import app


class RecommendationHttpApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def valid_payload(self, **overrides):
        payload = {"origin": "회기역", "transport_mode": "public_transit", "max_travel_time_minutes": 30, "time_slot": "evening", "purpose": "food"}
        payload.update(overrides)
        return payload

    def test_healthz_returns_fixture_status(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "fixture": True})

    def test_valid_recommendation_returns_transparent_capped_fixture_response(self):
        response = self.client.post("/v1/recommendations", json=self.valid_payload())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result_status"], "ok")
        self.assertEqual(body["eligible_count"], 6)
        self.assertEqual(len(body["recommendations"]), 5)
        self.assertEqual(body["ranking_basis"], "F0-public-rule")
        self.assertTrue(body["fixture"])
        self.assertIn("실시간 대중교통", body["limitations"])

    def test_purpose_change_changes_first_recommendation(self):
        food = self.client.post("/v1/recommendations", json=self.valid_payload(purpose="food"))
        cafe = self.client.post("/v1/recommendations", json=self.valid_payload(purpose="cafe"))
        self.assertEqual(food.status_code, 200)
        self.assertEqual(cafe.status_code, 200)
        self.assertNotEqual(food.json()["recommendations"][0]["id"], cafe.json()["recommendations"][0]["id"])

    def test_invalid_transport_purpose_and_time_return_422(self):
        for field, value in {"transport_mode": "walking", "purpose": "unknown", "max_travel_time_minutes": 25}.items():
            with self.subTest(field=field):
                response = self.client.post("/v1/recommendations", json=self.valid_payload(**{field: value}))
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
