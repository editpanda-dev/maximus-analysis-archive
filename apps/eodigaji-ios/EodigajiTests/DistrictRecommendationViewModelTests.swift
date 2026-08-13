import CoreLocation
import XCTest
@testable import Eodigaji

@MainActor
final class DistrictRecommendationViewModelTests: XCTestCase {
    func testSelectingDistrictShowsOnlyThatDistrictsExistingPlacesAndBackKeepsDistricts() async {
        let districts = [
            Self.district(name: "모현동", places: [Self.place(name: "모현식당")]),
            Self.district(name: "죽전동", places: [Self.place(name: "죽전카페")])
        ]
        let viewModel = RecommendationViewModel(
            districtService: StubDistrictRecommendationService(result: .success(districts)),
            selectedOrigin: Self.origin
        )

        await viewModel.recommendDistrictsLive()
        viewModel.selectDistrict(viewModel.liveDistricts[1])

        XCTAssertEqual(viewModel.selectedDistrict?.places.map(\.placeName), ["죽전카페"])

        viewModel.dismissDistrictPlaces()

        XCTAssertEqual(viewModel.liveDistricts, districts)
        XCTAssertNil(viewModel.selectedDistrict)
    }

    func testDistrictFailureClearsPreviousDistrictsWithoutLiveRecommendationFallback() async {
        let viewModel = RecommendationViewModel(
            districtService: SequencedDistrictRecommendationService(
                results: [
                    .success([Self.district(name: "모현동", places: [Self.place(name: "모현식당")])]),
                    .failure(StubError.unavailable)
                ]
            ),
            selectedOrigin: Self.origin
        )

        await viewModel.recommendDistrictsLive()
        await viewModel.recommendDistrictsLive()

        XCTAssertTrue(viewModel.liveDistricts.isEmpty)
        XCTAssertNil(viewModel.selectedDistrict)
        XCTAssertNotNil(viewModel.liveError)
        XCTAssertFalse(viewModel.shouldShowResults)
    }

    func testDistrictResultKeepsRequestSnapshotsWhenConditionsChangeWhileLoading() async {
        let service = PendingDistrictRecommendationService()
        let viewModel = RecommendationViewModel(
            districtService: service,
            selectedOrigin: Self.origin,
            maxTravelTimeMinutes: .twenty,
            purpose: .cafe
        )

        let request = Task { await viewModel.recommendDistrictsLive() }
        await service.waitUntilRequested()
        let newerOrigin = OriginLocation(
            name: "새 출발지",
            coordinate: CLLocationCoordinate2D(latitude: 37.5665, longitude: 126.9780),
            source: .mapPin
        )
        viewModel.selectOrigin(newerOrigin)
        viewModel.maxTravelTimeMinutes = .sixty
        viewModel.purpose = .culture
        service.complete(with: .success([Self.district(name: "모현동", places: [Self.place(name: "모현식당")])]))
        await request.value

        XCTAssertEqual(service.receivedOrigin, Self.origin)
        XCTAssertEqual(service.receivedPurpose, .cafe)
        XCTAssertEqual(service.receivedMaxTravelTime, .twenty)
        XCTAssertEqual(viewModel.liveResultsOrigin, Self.origin)
        XCTAssertEqual(viewModel.liveResultsMaxTravelTime, .twenty)
        XCTAssertEqual(viewModel.selectedOrigin, newerOrigin)
    }

    private static let origin = OriginLocation(
        name: "모현 한국외대",
        coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
        source: .searchedPlace
    )

    private static func district(name: String, places: [LiveRecommendation]) -> LiveDistrictRecommendation {
        LiveDistrictRecommendation(
            districtName: name,
            fastestTravelTime: 1_240,
            placeCount: places.count,
            places: places
        )
    }

    private static func place(name: String) -> LiveRecommendation {
        LiveRecommendation(
            placeName: name,
            address: "경기 용인시",
            destinationCoordinate: CLLocationCoordinate2D(latitude: 37.34, longitude: 127.27),
            expectedTravelTime: 1_240,
            distanceMeters: 4_200,
            routeSteps: []
        )
    }
}

@MainActor
private final class StubDistrictRecommendationService: DistrictRecommendationServicing {
    private let result: Result<[LiveDistrictRecommendation], Error>

    init(result: Result<[LiveDistrictRecommendation], Error>) {
        self.result = result
    }

    func recommendDistricts(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveDistrictRecommendation] {
        try result.get()
    }
}

@MainActor
private final class SequencedDistrictRecommendationService: DistrictRecommendationServicing {
    private var results: [Result<[LiveDistrictRecommendation], Error>]

    init(results: [Result<[LiveDistrictRecommendation], Error>]) {
        self.results = results
    }

    func recommendDistricts(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveDistrictRecommendation] {
        try results.removeFirst().get()
    }
}

@MainActor
private final class PendingDistrictRecommendationService: DistrictRecommendationServicing {
    private var continuation: CheckedContinuation<[LiveDistrictRecommendation], Error>?
    private var requestWaiters: [CheckedContinuation<Void, Never>] = []
    private(set) var receivedOrigin: OriginLocation?
    private(set) var receivedPurpose: Purpose?
    private(set) var receivedMaxTravelTime: MaxTravelTimeMinutes?

    func recommendDistricts(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveDistrictRecommendation] {
        receivedOrigin = origin
        receivedPurpose = purpose
        receivedMaxTravelTime = maxTravelTime
        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            requestWaiters.forEach { $0.resume() }
            requestWaiters = []
        }
    }

    func waitUntilRequested() async {
        guard continuation == nil else { return }
        await withCheckedContinuation { requestWaiters.append($0) }
    }

    func complete(with result: Result<[LiveDistrictRecommendation], Error>) {
        let continuation = continuation
        self.continuation = nil
        continuation?.resume(with: result)
    }
}

private enum StubError: Error {
    case unavailable
}
