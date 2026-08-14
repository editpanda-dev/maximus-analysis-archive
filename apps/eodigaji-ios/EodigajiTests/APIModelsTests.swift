import XCTest
@testable import Eodigaji

final class APIModelsTests: XCTestCase {
    func testThirtyMinuteSelectionDisplaysTwentyToThirtyMinuteRecommendationWindow() {
        XCTAssertEqual(MaxTravelTimeMinutes.thirty.recommendationWindowLabel, "20–30분")
    }

    func testRecommendationRequestUsesExactSnakeCaseContract() throws {
        let request = RecommendationRequest(
            origin: "회기역",
            transportMode: .publicTransit,
            maxTravelTimeMinutes: .thirty,
            timeSlot: .evening,
            purpose: .cafe
        )

        let encoder = JSONEncoder()
        let json = try JSONSerialization.jsonObject(with: encoder.encode(request)) as? [String: Any]

        XCTAssertEqual(json?["origin"] as? String, "회기역")
        XCTAssertEqual(json?["transport_mode"] as? String, "public_transit")
        XCTAssertEqual(json?["max_travel_time_minutes"] as? Int, 30)
        XCTAssertEqual(json?["time_slot"] as? String, "evening")
        XCTAssertEqual(json?["purpose"] as? String, "cafe")
    }

    func testRecommendationResponseDecodesRecommendationAndFixtureMetadata() throws {
        let data = Data(
            """
            {
              "result_status": "ok",
              "eligible_count": 5,
              "recommendations": [
                {
                  "id": "cafe_bukchon",
                  "name": "북촌 카페거리",
                  "district": "종로구",
                  "journey_time_minutes": 28,
                  "route_status": "available_verified",
                  "cost_status": "available",
                  "cost_won": 1500,
                  "tags": ["조용한", "산책"],
                  "reason": "카페 목적의 fixture 프로필에서 북촌 카페거리를 우선한 F0 규칙입니다.",
                  "signal": "fixture_cafe_profile",
                  "method": "fixture_rule_v1",
                  "vintage": "F0-fixture-v1"
                }
              ],
              "ranking_basis": "F0-public-rule",
              "fixture": true,
              "limitations": "데모 fixture이며 실시간 대중교통 정보가 아닙니다."
            }
            """.utf8
        )

        let decoder = JSONDecoder()
        let response = try decoder.decode(RecommendationResponse.self, from: data)

        XCTAssertEqual(response.resultStatus, .ok)
        XCTAssertEqual(response.eligibleCount, 5)
        XCTAssertEqual(response.recommendations.count, 1)
        XCTAssertEqual(response.recommendations[0].journeyTimeMinutes, 28)
        XCTAssertEqual(response.recommendations[0].costWon, 1500)
        XCTAssertEqual(response.rankingBasis, .f0PublicRule)
        XCTAssertTrue(response.fixture)
        XCTAssertEqual(response.limitations, "데모 fixture이며 실시간 대중교통 정보가 아닙니다.")
    }
}
