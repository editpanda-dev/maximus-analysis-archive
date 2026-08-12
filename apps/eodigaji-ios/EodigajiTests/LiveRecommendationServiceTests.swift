import CoreLocation
import MapKit
import XCTest
@testable import Eodigaji

@MainActor
final class LiveRecommendationServiceTests: XCTestCase {
    func testTransitRoutesOverLimitAndWithoutTransitAreExcluded() async throws {
        let candidates = [
            candidate(name: "가까운 카페", longitude: 127.01),
            candidate(name: "먼 카페", longitude: 127.02),
            candidate(name: "경로 없는 카페", longitude: 127.03),
        ]
        let search = StubLivePlaceSearchPort(candidates: candidates)
        let directions = StubLiveDirectionsPort { request in
            guard request.transportType == .transit else { return nil }

            switch request.destination.longitude {
            case 127.01:
                return Self.route(travelTime: 29 * 60)
            case 127.02:
                return Self.route(travelTime: 31 * 60)
            default:
                return nil
            }
        }
        let service = LiveRecommendationService(searchPort: search, directionsPort: directions)

        let results = try await service.recommend(
            from: Self.origin,
            purpose: .cafe,
            maxTravelTime: .thirty
        )

        XCTAssertEqual(results.map(\.placeName), ["가까운 카페"])
        XCTAssertEqual(directions.requests.map(\.transportType), [.transit, .transit, .transit])
    }

    func testRouteExactlyAtTimeLimitIsIncluded() async throws {
        let search = StubLivePlaceSearchPort(candidates: [candidate(name: "경계 카페", longitude: 127.04)])
        let directions = StubLiveDirectionsPort { _ in Self.route(travelTime: 30 * 60) }
        let service = LiveRecommendationService(searchPort: search, directionsPort: directions)

        let results = try await service.recommend(
            from: Self.origin,
            purpose: .cafe,
            maxTravelTime: .thirty
        )

        XCTAssertEqual(results.map(\.placeName), ["경계 카페"])
        XCTAssertEqual(results.map(\.journeyTimeMinutes), [30])
    }

    func testSearchRegionIsCenteredOnSelectedOrigin() async throws {
        let search = StubLivePlaceSearchPort(candidates: [])
        let directions = StubLiveDirectionsPort { _ in nil }
        let service = LiveRecommendationService(searchPort: search, directionsPort: directions)
        let first = OriginLocation(
            name: "첫 출발지",
            coordinate: CLLocationCoordinate2D(latitude: 37.50, longitude: 127.00),
            source: .mapPin
        )
        let second = OriginLocation(
            name: "둘째 출발지",
            coordinate: CLLocationCoordinate2D(latitude: 37.60, longitude: 127.10),
            source: .searchedPlace
        )

        _ = try await service.recommend(from: first, purpose: .food, maxTravelTime: .twenty)
        _ = try await service.recommend(from: second, purpose: .food, maxTravelTime: .twenty)

        XCTAssertEqual(search.requests.map { $0.region.center.latitude }, [37.50, 37.60])
        XCTAssertEqual(search.requests.map { $0.region.center.longitude }, [127.00, 127.10])
    }

    func testRecommendationsUsePurposeQueryAndSortByTimeThenName() async throws {
        let search = StubLivePlaceSearchPort(candidates: [
            candidate(name: "나 카페", longitude: 127.11),
            candidate(name: "다 카페", longitude: 127.12),
            candidate(name: "가 카페", longitude: 127.13),
        ])
        let directions = StubLiveDirectionsPort { request in
            let travelTime = request.destination.longitude == 127.11 ? 10 * 60 : 20 * 60
            return Self.route(travelTime: TimeInterval(travelTime))
        }
        let service = LiveRecommendationService(searchPort: search, directionsPort: directions)

        let results = try await service.recommend(
            from: Self.origin,
            purpose: .cafe,
            maxTravelTime: .thirty
        )

        XCTAssertEqual(search.requests.map(\.query), ["카페"])
        XCTAssertEqual(results.map(\.placeName), ["나 카페", "가 카페", "다 카페"])
    }

    func testRouteDetailsArePreservedWithoutFabricatedTransitData() async throws {
        let search = StubLivePlaceSearchPort(candidates: [
            LivePlaceCandidate(
                name: "문화 공간",
                address: "서울특별시 종로구",
                coordinate: CLLocationCoordinate2D(latitude: 37.57, longitude: 126.98)
            ),
        ])
        let route = LiveTransitRoute(
            expectedTravelTime: 12 * 60,
            distanceMeters: 4_321,
            steps: [
                LiveRouteStep(instructions: "정류장까지 걷기", distanceMeters: 210, transportType: .walking),
                LiveRouteStep(instructions: "대중교통 이용", distanceMeters: 4_000, transportType: .transit),
            ]
        )
        let service = LiveRecommendationService(
            searchPort: search,
            directionsPort: StubLiveDirectionsPort { _ in route }
        )

        let results = try await service.recommend(
            from: Self.origin,
            purpose: .culture,
            maxTravelTime: .twenty
        )
        let result = try XCTUnwrap(results.first)

        XCTAssertEqual(result.address, "서울특별시 종로구")
        XCTAssertEqual(result.distanceMeters, 4_321)
        XCTAssertEqual(result.routeSteps, route.steps)
    }

    func testDirectionsRequestsAreBoundedAndResultsStayStableWhenCompletionOrderDiffers() async throws {
        let candidates = [
            candidate(name: "다 카페", longitude: 127.21),
            candidate(name: "나 카페", longitude: 127.22),
            candidate(name: "가 카페", longitude: 127.23),
            candidate(name: "라 카페", longitude: 127.24),
            candidate(name: "마 카페", longitude: 127.25),
        ]
        let directions = ControlledLiveDirectionsPort(
            routes: [
                127.21: Self.route(travelTime: 20 * 60),
                127.22: Self.route(travelTime: 10 * 60),
                127.23: Self.route(travelTime: 20 * 60),
                127.24: Self.route(travelTime: 30 * 60),
                127.25: Self.route(travelTime: 5 * 60),
            ]
        )
        let service = LiveRecommendationService(
            searchPort: StubLivePlaceSearchPort(candidates: candidates),
            directionsPort: directions,
            maximumConcurrentDirections: 2
        )

        let recommendationTask = Task { @MainActor in
            try await service.recommend(
                from: Self.origin,
                purpose: .cafe,
                maxTravelTime: .thirty
            )
        }

        guard await waitForStartedCount(2, in: directions) else {
            directions.enableAutomaticCompletion()
            _ = try await recommendationTask.value
            XCTFail("Expected two concurrent directions requests")
            return
        }

        XCTAssertEqual(directions.maximumActiveRequestCount, 2)
        directions.finish(longitude: 127.22)
        guard await waitForStartedCount(3, in: directions) else {
            directions.enableAutomaticCompletion()
            _ = try await recommendationTask.value
            XCTFail("Expected a third request after one slot became available")
            return
        }
        directions.finish(longitude: 127.23)
        guard await waitForStartedCount(4, in: directions) else {
            directions.enableAutomaticCompletion()
            _ = try await recommendationTask.value
            XCTFail("Expected a fourth request after one slot became available")
            return
        }
        directions.finish(longitude: 127.21)
        guard await waitForStartedCount(5, in: directions) else {
            directions.enableAutomaticCompletion()
            _ = try await recommendationTask.value
            XCTFail("Expected a fifth request after one slot became available")
            return
        }
        directions.finish(longitude: 127.24)
        directions.finish(longitude: 127.25)

        let results = try await recommendationTask.value

        XCTAssertEqual(directions.maximumActiveRequestCount, 2)
        XCTAssertEqual(results.map(\.placeName), ["마 카페", "나 카페", "가 카페", "다 카페", "라 카페"])
    }

    private func waitForStartedCount(
        _ expectedCount: Int,
        in directions: ControlledLiveDirectionsPort
    ) async -> Bool {
        for _ in 0..<500 {
            if directions.startedCount >= expectedCount {
                return true
            }
            try? await Task.sleep(nanoseconds: 1_000_000)
        }
        return false
    }

    private static let origin = OriginLocation(
        name: "출발지",
        coordinate: CLLocationCoordinate2D(latitude: 37.55, longitude: 127.00),
        source: .currentDevice
    )

    private static func route(travelTime: TimeInterval) -> LiveTransitRoute {
        LiveTransitRoute(expectedTravelTime: travelTime, distanceMeters: 1_000, steps: [])
    }

    private func candidate(name: String, longitude: CLLocationDegrees) -> LivePlaceCandidate {
        LivePlaceCandidate(
            name: name,
            address: "서울",
            coordinate: CLLocationCoordinate2D(latitude: 37.56, longitude: longitude)
        )
    }
}

@MainActor
private final class StubLivePlaceSearchPort: LivePlaceSearchPort {
    let candidates: [LivePlaceCandidate]
    private(set) var requests: [LivePlaceSearchRequest] = []

    init(candidates: [LivePlaceCandidate]) {
        self.candidates = candidates
    }

    func search(_ request: LivePlaceSearchRequest) async throws -> [LivePlaceCandidate] {
        requests.append(request)
        return candidates
    }
}

@MainActor
private final class StubLiveDirectionsPort: LiveDirectionsPort {
    private let response: (LiveDirectionsRequest) throws -> LiveTransitRoute?
    private(set) var requests: [LiveDirectionsRequest] = []

    init(response: @escaping (LiveDirectionsRequest) throws -> LiveTransitRoute?) {
        self.response = response
    }

    func route(for request: LiveDirectionsRequest) async throws -> LiveTransitRoute? {
        requests.append(request)
        return try response(request)
    }
}

@MainActor
private final class ControlledLiveDirectionsPort: LiveDirectionsPort {
    private let routes: [CLLocationDegrees: LiveTransitRoute]
    private var pending: [CLLocationDegrees: CheckedContinuation<LiveTransitRoute?, Never>] = [:]
    private var automaticallyCompletes = false
    private(set) var startedCount = 0
    private(set) var maximumActiveRequestCount = 0
    private var activeRequestCount = 0

    init(routes: [CLLocationDegrees: LiveTransitRoute]) {
        self.routes = routes
    }

    func route(for request: LiveDirectionsRequest) async throws -> LiveTransitRoute? {
        let longitude = request.destination.longitude
        startedCount += 1
        activeRequestCount += 1
        maximumActiveRequestCount = max(maximumActiveRequestCount, activeRequestCount)

        if automaticallyCompletes {
            activeRequestCount -= 1
            return routes[longitude]
        }

        return await withCheckedContinuation { continuation in
            pending[longitude] = continuation
        }
    }

    func finish(longitude: CLLocationDegrees) {
        guard let continuation = pending.removeValue(forKey: longitude) else { return }
        activeRequestCount -= 1
        continuation.resume(returning: routes[longitude])
    }

    func enableAutomaticCompletion() {
        automaticallyCompletes = true
        let suspended = pending
        pending.removeAll()
        activeRequestCount -= suspended.count
        for (longitude, continuation) in suspended {
            continuation.resume(returning: routes[longitude])
        }
    }

}
