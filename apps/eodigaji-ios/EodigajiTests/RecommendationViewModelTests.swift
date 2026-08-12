import XCTest
@testable import Eodigaji

@MainActor
final class RecommendationViewModelTests: XCTestCase {
    func testRecommendMapsCurrentSelectionsToRequestAndStoresResponse() async throws {
        let expectedResponse = Self.sampleResponse
        let service = StubRecommendationService(result: .success(expectedResponse))
        let viewModel = RecommendationViewModel(service: service)

        viewModel.origin = "청량리역"
        viewModel.transportMode = .publicTransit
        viewModel.maxTravelTimeMinutes = .sixty
        viewModel.timeSlot = .morning
        viewModel.purpose = .culture

        await viewModel.recommend()

        let request = await service.receivedRequest
        XCTAssertEqual(
            request,
            RecommendationRequest(
                origin: "청량리역",
                transportMode: .publicTransit,
                maxTravelTimeMinutes: .sixty,
                timeSlot: .morning,
                purpose: .culture
            )
        )
        XCTAssertEqual(viewModel.response, expectedResponse)
        XCTAssertNil(viewModel.error)
        XCTAssertFalse(viewModel.isLoading)
    }

    func testRecommendStoresClientErrorAndClearsResults() async throws {
        let service = StubRecommendationService(
            result: .failure(StubError.unavailable)
        )
        let viewModel = RecommendationViewModel(service: service)

        await viewModel.recommend()

        XCTAssertNil(viewModel.response)
        XCTAssertNotNil(viewModel.error)
        XCTAssertTrue(viewModel.errorMessage?.contains("추천") == true)
        XCTAssertFalse(viewModel.isLoading)
    }

    private static let sampleResponse = RecommendationResponse(
        resultStatus: .ok,
        eligibleCount: 1,
        recommendations: [
            Recommendation(
                id: "culture_001",
                name: "서울숲",
                district: "성동구",
                journeyTimeMinutes: 38,
                routeStatus: .availableVerified,
                costStatus: .unavailable,
                costWon: nil,
                tags: ["산책", "문화"],
                reason: "문화 목적에 맞는 fixture 추천입니다.",
                signal: "fixture_culture_profile",
                method: "fixture_rule_v1",
                vintage: "F0-fixture-v1"
            )
        ],
        rankingBasis: .f0PublicRule,
        fixture: true,
        limitations: "데모 fixture이며 실시간 대중교통 정보가 아닙니다."
    )
}

private actor StubRecommendationService: RecommendationServicing {
    enum Result {
        case success(RecommendationResponse)
        case failure(Error)
    }

    private let result: Result
    private(set) var receivedRequest: RecommendationRequest?

    init(result: Result) {
        self.result = result
    }

    func recommendations(for request: RecommendationRequest) async throws -> RecommendationResponse {
        receivedRequest = request

        switch result {
        case let .success(response):
            return response
        case let .failure(error):
            throw error
        }
    }
}

private enum StubError: Error {
    case unavailable
}
