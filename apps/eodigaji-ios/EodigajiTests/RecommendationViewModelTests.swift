import CoreLocation
import MapKit
import XCTest
@testable import Eodigaji

@MainActor
final class RecommendationViewModelTests: XCTestCase {
    func testFreshContentViewModelStartsWithoutDistrictResults() {
        let viewModel = RecommendationViewModel(districtService: DistrictStub())

        XCTAssertFalse(viewModel.shouldShowResults)
        XCTAssertTrue(viewModel.liveDistricts.isEmpty)
        XCTAssertNil(viewModel.selectedDistrict)
    }

    func testRecommendMapsCurrentSelectionsToLegacyRequestAndStoresResponse() async {
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
        XCTAssertTrue(viewModel.shouldShowResults)
        XCTAssertNil(viewModel.error)
        XCTAssertFalse(viewModel.isLoading)
    }

    func testLegacyDismissResultsPreservesResponse() async {
        let viewModel = RecommendationViewModel(
            service: StubRecommendationService(result: .success(Self.sampleResponse))
        )

        await viewModel.recommend()
        viewModel.dismissResults()

        XCTAssertFalse(viewModel.shouldShowResults)
        XCTAssertEqual(viewModel.response, Self.sampleResponse)
    }

    func testLegacyRecommendStoresClientErrorAndClearsResults() async {
        let viewModel = RecommendationViewModel(
            service: StubRecommendationService(result: .failure(StubError.unavailable))
        )

        await viewModel.recommend()

        XCTAssertNil(viewModel.response)
        XCTAssertNotNil(viewModel.error)
        XCTAssertTrue(viewModel.errorMessage?.contains("추천") == true)
        XCTAssertFalse(viewModel.isLoading)
    }

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

    func testLiveBackendValidationErrorIsShownWithoutReplacingResults() async {
        let viewModel = RecommendationViewModel(
            liveService: StubLiveRecommendationService(
                result: .failure(
                    KakaoLiveRecommendationAPIError.backend(
                        statusCode: 422,
                        message: "origin coordinates must be within supported South Korea regions"
                    )
                )
            ),
            selectedOrigin: OriginLocation(
                name: "지도 핀",
                coordinate: CLLocationCoordinate2D(latitude: 40.7128, longitude: -74.006),
                source: .mapPin
            )
        )

        await viewModel.recommendLive()

        XCTAssertTrue(viewModel.liveResults.isEmpty)
        XCTAssertFalse(viewModel.shouldShowResults)
        XCTAssertTrue(viewModel.liveErrorMessage?.contains("supported South Korea") == true)
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
            maxTravelTimeMinutes: .twenty,
            purpose: .cafe
        )

        let request = Task { await viewModel.recommendLive() }
        await liveService.waitUntilRequested()
        viewModel.selectOrigin(newerOrigin)
        viewModel.maxTravelTimeMinutes = .sixty
        viewModel.purpose = .culture
        liveService.complete(with: .success([Self.sampleRecommendation]))
        await request.value

        XCTAssertEqual(viewModel.selectedOrigin, newerOrigin)
        XCTAssertEqual(viewModel.liveResultsOrigin, firstOrigin)
        XCTAssertEqual(viewModel.liveResultsMaxTravelTime, .twenty)
        XCTAssertEqual(liveService.receivedPurpose, .cafe)
        XCTAssertEqual(viewModel.liveResults, [Self.sampleRecommendation])
    }

    func testPendingOriginSearchDoesNotPublishResultsAfterQueryChanges() async {
        let searchService = PendingViewModelOriginSearchService()
        let viewModel = RecommendationViewModel(
            liveService: StubLiveRecommendationService(result: .success([])),
            originSearchService: searchService
        )
        let staleResult = OriginLocation(
            name: "이전 검색 결과",
            coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
            source: .searchedPlace
        )
        viewModel.originQuery = "첫 검색어"

        let request = Task { await viewModel.searchOrigins() }
        await searchService.waitUntilRequested()
        viewModel.originQuery = "새 검색어"
        searchService.complete(with: .success([staleResult]))
        await request.value

        XCTAssertEqual(viewModel.originQuery, "새 검색어")
        XCTAssertTrue(viewModel.originSearchResults.isEmpty)
        XCTAssertFalse(viewModel.hasCompletedOriginSearch)
        XCTAssertNil(viewModel.originSearchError)
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

@MainActor
private final class DistrictStub: DistrictRecommendationServicing {
    func recommendDistricts(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveDistrictRecommendation] {
        []
    }
}

private actor StubRecommendationService: RecommendationServicing {
    private let result: Result<RecommendationResponse, Error>
    private(set) var receivedRequest: RecommendationRequest?

    init(result: Result<RecommendationResponse, Error>) {
        self.result = result
    }

    func recommendations(for request: RecommendationRequest) async throws -> RecommendationResponse {
        receivedRequest = request
        return try result.get()
    }
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
    private(set) var receivedPurpose: Purpose?

    func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation] {
        receivedPurpose = purpose
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

    func complete(with result: Result<[LiveRecommendation], Error>) {
        let continuation = continuation
        self.continuation = nil
        continuation?.resume(with: result)
    }
}

@MainActor
private final class PendingViewModelOriginSearchService: OriginSearching {
    private var continuation: CheckedContinuation<[OriginLocation], Error>?
    private var requestWaiters: [CheckedContinuation<Void, Never>] = []

    func search(query: String, region: MKCoordinateRegion?) async throws -> [OriginLocation] {
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

    func complete(with result: Result<[OriginLocation], Error>) {
        let continuation = continuation
        self.continuation = nil
        continuation?.resume(with: result)
    }
}

private enum StubError: Error {
    case unavailable
}
