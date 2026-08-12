import CoreLocation
import XCTest
@testable import Eodigaji

@MainActor
final class LocationServiceTests: XCTestCase {
    func testCurrentLocationReturnsCurrentDeviceOrigin() async throws {
        let result = try await StubLocationService.current.requestCurrentLocation()

        XCTAssertEqual(result.name, "현재 위치")
        XCTAssertEqual(result.coordinate.latitude, 37.5901)
        XCTAssertEqual(result.coordinate.longitude, 127.0560)
        XCTAssertEqual(result.source, .currentDevice)
    }

    func testCurrentLocationThrowsPermissionDeniedWhenLocationAccessIsDenied() async {
        do {
            _ = try await StubLocationService.denied.requestCurrentLocation()
            XCTFail("Expected denied location permission to throw an error")
        } catch {
            XCTAssertEqual(error as? LocationServiceError, .permissionDenied)
        }
    }

    func testOverlappingCurrentLocationRequestsShareOneDeviceLocationRequest() async throws {
        let manager = PendingLocationManager()
        let service = LocationService(locationManager: manager)

        async let firstResult = service.requestCurrentLocation()
        await Task.yield()
        async let secondResult = service.requestCurrentLocation()
        await Task.yield()

        XCTAssertEqual(manager.requestLocationCallCount, 1)
        manager.returnCoordinate(CLLocationCoordinate2D(latitude: 37.5665, longitude: 126.9780))

        let first = try await firstResult
        let second = try await secondResult
        XCTAssertEqual(first.coordinate.latitude, 37.5665)
        XCTAssertEqual(second.coordinate.longitude, 126.9780)
    }
}

@MainActor
private enum StubLocationService {
    static let current: any LocationServicing = LocationService(
        locationManager: StubLocationManager(
            authorizationStatus: .authorizedWhenInUse,
            coordinate: CLLocationCoordinate2D(latitude: 37.5901, longitude: 127.0560)
        )
    )

    static let denied: any LocationServicing = LocationService(
        locationManager: StubLocationManager(authorizationStatus: .denied)
    )
}

@MainActor
private final class StubLocationManager: LocationManaging {
    let authorizationStatus: CLAuthorizationStatus
    let coordinate: CLLocationCoordinate2D?

    init(authorizationStatus: CLAuthorizationStatus, coordinate: CLLocationCoordinate2D? = nil) {
        self.authorizationStatus = authorizationStatus
        self.coordinate = coordinate
    }

    func requestWhenInUseAuthorization(onChange: @escaping (CLAuthorizationStatus) -> Void) {
        onChange(authorizationStatus)
    }

    func requestLocation(
        onSuccess: @escaping (CLLocationCoordinate2D) -> Void,
        onFailure: @escaping (Error) -> Void
    ) {
        guard let coordinate else {
            onFailure(LocationServiceError.locationUnavailable)
            return
        }

        onSuccess(coordinate)
    }
}

@MainActor
private final class PendingLocationManager: LocationManaging {
    let authorizationStatus: CLAuthorizationStatus = .authorizedWhenInUse
    private(set) var requestLocationCallCount = 0
    private var successHandler: ((CLLocationCoordinate2D) -> Void)?

    func requestWhenInUseAuthorization(onChange: @escaping (CLAuthorizationStatus) -> Void) {
        onChange(authorizationStatus)
    }

    func requestLocation(
        onSuccess: @escaping (CLLocationCoordinate2D) -> Void,
        onFailure: @escaping (Error) -> Void
    ) {
        requestLocationCallCount += 1
        successHandler = onSuccess
    }

    func returnCoordinate(_ coordinate: CLLocationCoordinate2D) {
        successHandler?(coordinate)
        successHandler = nil
    }
}
