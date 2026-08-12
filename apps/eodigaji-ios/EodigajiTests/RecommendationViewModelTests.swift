import CoreLocation
import MapKit
import XCTest
@testable import Eodigaji

@MainActor
final class RecommendationViewModelTests: XCTestCase {
    func testRecommendLivePassesSelectedMapOriginAndConditionsToLiveService() async {
        let expectedRecommendation = Self.sampleRecommendation
        let service = StubLiveRecommendationService(result: .success([expectedRecommendation]))
        let viewModel = RecommendationViewModel(liveService: service)
        let selectedOrigin = OriginLocation(
            name: "지도 핀",
            coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
            source: .mapPin
        )

        viewModel.selectOrigin(selectedOrigin)
        viewModel.purpose = .culture
        viewModel.maxTravelTimeMinutes = .sixty

        await viewModel.recommendLive()

        XCTAssertEqual(service.receivedOrigin, selectedOrigin)
        XCTAssertEqual(service.receivedPurpose, .culture)
        XCTAssertEqual(service.receivedMaxTravelTime, .sixty)
        XCTAssertEqual(viewModel.liveResults, [expectedRecommendation])
        XCTAssertTrue(viewModel.shouldShowResults)
        XCTAssertNil(viewModel.liveError)
        XCTAssertFalse(viewModel.isLoading)
    }

    func testDismissResultsReturnsToSameLiveConditionsWithoutDiscardingResults() async {
        let service = StubLiveRecommendationService(result: .success([Self.sampleRecommendation]))
        let viewModel = RecommendationViewModel(liveService: service)
        let selectedOrigin = OriginLocation(
            name: "모현 한국외대",
            coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
            source: .searchedPlace
        )
        viewModel.selectOrigin(selectedOrigin)
        viewModel.purpose = .rest
        viewModel.maxTravelTimeMinutes = .forty

        await viewModel.recommendLive()
        viewModel.dismissResults()

        XCTAssertFalse(viewModel.shouldShowResults)
        XCTAssertEqual(viewModel.selectedOrigin, selectedOrigin)
        XCTAssertEqual(viewModel.purpose, .rest)
        XCTAssertEqual(viewModel.maxTravelTimeMinutes, .forty)
        XCTAssertEqual(viewModel.liveResults, [Self.sampleRecommendation])
    }

    func testLiveFailureClearsPreviousResultsInsteadOfUsingFixtureFallback() async {
        let service = SequencedLiveRecommendationService(
            results: [
                .success([Self.sampleRecommendation]),
                .failure(StubError.unavailable)
            ]
        )
        let viewModel = RecommendationViewModel(liveService: service)
        viewModel.selectOrigin(
            OriginLocation(
                name: "현재 위치",
                coordinate: CLLocationCoordinate2D(latitude: 37.5665, longitude: 126.9780),
                source: .currentDevice
            )
        )

        await viewModel.recommendLive()
        await viewModel.recommendLive()

        XCTAssertTrue(viewModel.liveResults.isEmpty)
        XCTAssertNotNil(viewModel.liveError)
        XCTAssertFalse(viewModel.shouldShowResults)
        XCTAssertFalse(viewModel.isLoading)
    }

    func testRequestCurrentLocationSelectsReturnedDeviceOrigin() async {
        let expectedOrigin = OriginLocation(
            name: "현재 위치",
            coordinate: CLLocationCoordinate2D(latitude: 37.5665, longitude: 126.9780),
            source: .currentDevice
        )
        let locationService = StubViewModelLocationService(result: .success(expectedOrigin))
        let viewModel = RecommendationViewModel(
            liveService: StubLiveRecommendationService(result: .success([])),
            locationService: locationService
        )

        await viewModel.requestCurrentLocation()

        XCTAssertEqual(locationService.requestCount, 1)
        XCTAssertEqual(viewModel.selectedOrigin, expectedOrigin)
        XCTAssertNil(viewModel.originError)
        XCTAssertFalse(viewModel.isResolvingOrigin)
    }

    func testSearchOriginsStoresCoordinateResultsForSelection() async {
        let expectedOrigin = OriginLocation(
            name: "모현 한국외대",
            coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
            source: .searchedPlace
        )
        let searchService = StubViewModelOriginSearchService(result: .success([expectedOrigin]))
        let viewModel = RecommendationViewModel(
            liveService: StubLiveRecommendationService(result: .success([])),
            originSearchService: searchService
        )
        viewModel.originQuery = "  모현 한국외대  "

        await viewModel.searchOrigins()

        XCTAssertEqual(searchService.receivedQuery, "모현 한국외대")
        XCTAssertEqual(viewModel.originSearchResults, [expectedOrigin])
        XCTAssertTrue(viewModel.hasCompletedOriginSearch)
        XCTAssertNil(viewModel.originSearchError)
        XCTAssertFalse(viewModel.isSearchingOrigins)
    }

    func testEmptyLiveResultShowsHonestNoRouteState() async {
        let viewModel = RecommendationViewModel(
            liveService: StubLiveRecommendationService(result: .success([])),
            selectedOrigin: OriginLocation(
                name: "지도 핀",
                coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
                source: .mapPin
            )
        )

        await viewModel.recommendLive()

        XCTAssertTrue(viewModel.shouldShowResults)
        XCTAssertTrue(viewModel.liveResults.isEmpty)
        XCTAssertNil(viewModel.liveError)
    }

    func testPendingCurrentLocationDoesNotOverwriteNewerManualOrigin() async {
        let locationService = PendingViewModelLocationService()
        let viewModel = RecommendationViewModel(
            liveService: StubLiveRecommendationService(result: .success([])),
            locationService: locationService
        )
        let manualOrigin = OriginLocation(
            name: "수동 핀",
            coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
            source: .mapPin
        )
        let deviceOrigin = OriginLocation(
            name: "현재 위치",
            coordinate: CLLocationCoordinate2D(latitude: 37.5665, longitude: 126.9780),
            source: .currentDevice
        )

        let request = Task { await viewModel.requestCurrentLocation() }
        await locationService.waitUntilRequested()
        viewModel.selectOrigin(manualOrigin)
        locationService.complete(with: .success(deviceOrigin))
        await request.value

        XCTAssertEqual(viewModel.selectedOrigin, manualOrigin)
    }

    func testLiveResultsKeepOriginAndLimitUsedByPendingRequest() async {
        let liveService = PendingLiveRecommendationService()
        let firstOrigin = OriginLocation(
            name: "첫 출발지",
            coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
            source: .mapPin
        )
        let newerOrigin = OriginLocation(
            name: "새 출발지",
            coordinate: CLLocationCoordinate2D(latitude: 37.5665, longitude: 126.9780),
            source: .searchedPlace
        )
        let viewModel = RecommendationViewModel(
            liveService: liveService,
            selectedOrigin: firstOrigin,
            maxTravelTimeMinutes: .twenty
        )

        let request = Task { await viewModel.recommendLive() }
        await liveService.waitUntilRequested()
        viewModel.selectOrigin(newerOrigin)
        viewModel.maxTravelTimeMinutes = .sixty
        liveService.complete(with: .success([Self.sampleRecommendation]))
        await request.value

        XCTAssertEqual(viewModel.selectedOrigin, newerOrigin)
        XCTAssertEqual(viewModel.liveResultsOrigin, firstOrigin)
        XCTAssertEqual(viewModel.liveResultsMaxTravelTime, .twenty)
        XCTAssertEqual(viewModel.liveResults, [Self.sampleRecommendation])
    }

    private static let sampleRecommendation = LiveRecommendation(
        placeName: "서울숲",
        address: "서울 성동구 뚝섬로 273",
        destinationCoordinate: CLLocationCoordinate2D(latitude: 37.5444, longitude: 127.0374),
        expectedTravelTime: 2_280,
        distanceMeters: 12_300,
        routeSteps: [
            LiveRouteStep(
                instructions: "왕산로 정류장까지 도보",
                distanceMeters: 240,
                transportType: .walking
            )
        ]
    )
}

@MainActor
private final class StubLiveRecommendationService: LiveRecommendationServicing {
    private let result: Result<[LiveRecommendation], Error>
    private(set) var receivedOrigin: OriginLocation?
    private(set) var receivedPurpose: Purpose?
    private(set) var receivedMaxTravelTime: MaxTravelTimeMinutes?

    init(result: Result<[LiveRecommendation], Error>) {
        self.result = result
    }

    func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation] {
        receivedOrigin = origin
        receivedPurpose = purpose
        receivedMaxTravelTime = maxTravelTime
        return try result.get()
    }
}

@MainActor
private final class SequencedLiveRecommendationService: LiveRecommendationServicing {
    private var results: [Result<[LiveRecommendation], Error>]

    init(results: [Result<[LiveRecommendation], Error>]) {
        self.results = results
    }

    func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation] {
        try results.removeFirst().get()
    }
}

@MainActor
private final class StubViewModelLocationService: LocationServicing {
    private let result: Result<OriginLocation, Error>
    private(set) var requestCount = 0

    init(result: Result<OriginLocation, Error>) {
        self.result = result
    }

    func requestCurrentLocation() async throws -> OriginLocation {
        requestCount += 1
        return try result.get()
    }
}

@MainActor
private final class StubViewModelOriginSearchService: OriginSearching {
    private let result: Result<[OriginLocation], Error>
    private(set) var receivedQuery: String?

    init(result: Result<[OriginLocation], Error>) {
        self.result = result
    }

    func search(query: String, region: MKCoordinateRegion?) async throws -> [OriginLocation] {
        receivedQuery = query
        return try result.get()
    }
}

@MainActor
private final class PendingViewModelLocationService: LocationServicing {
    private var continuation: CheckedContinuation<OriginLocation, Error>?
    private var requestWaiters: [CheckedContinuation<Void, Never>] = []

    func requestCurrentLocation() async throws -> OriginLocation {
        try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            requestWaiters.forEach { $0.resume() }
            requestWaiters = []
        }
    }

    func waitUntilRequested() async {
        guard continuation == nil else { return }
        await withCheckedContinuation { requestWaiters.append($0) }
    }

    func complete(with result: Result<OriginLocation, Error>) {
        let continuation = continuation
        self.continuation = nil
        continuation?.resume(with: result)
    }
}

@MainActor
private final class PendingLiveRecommendationService: LiveRecommendationServicing {
    private var continuation: CheckedContinuation<[LiveRecommendation], Error>?
    private var requestWaiters: [CheckedContinuation<Void, Never>] = []

    func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation] {
        try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            requestWaiters.forEach { $0.resume() }
            requestWaiters = []
        }
    }

    func waitUntilRequested() async {
        guard continuation == nil else { return }
        await withCheckedContinuation { requestWaiters.append($0) }
    }

    func complete(with result: Result<[LiveRecommendation], Error>) {
        let continuation = continuation
        self.continuation = nil
        continuation?.resume(with: result)
    }
}

private enum StubError: Error {
    case unavailable
}
