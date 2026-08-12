import CoreLocation
import Foundation

public enum LocationServiceError: Error, Equatable, LocalizedError {
    case permissionDenied
    case locationUnavailable

    public var errorDescription: String? {
        switch self {
        case .permissionDenied:
            return "현재 위치 접근 권한이 필요합니다."
        case .locationUnavailable:
            return "현재 위치를 가져올 수 없습니다."
        }
    }
}

@MainActor
public protocol LocationServicing: AnyObject {
    func requestCurrentLocation() async throws -> OriginLocation
}

@MainActor
protocol LocationManaging: AnyObject {
    var authorizationStatus: CLAuthorizationStatus { get }

    func requestWhenInUseAuthorization(onChange: @escaping (CLAuthorizationStatus) -> Void)
    func requestLocation(
        onSuccess: @escaping (CLLocationCoordinate2D) -> Void,
        onFailure: @escaping (Error) -> Void
    )
}

@MainActor
public final class LocationService: LocationServicing {
    private let locationManager: any LocationManaging
    private var authorizationContinuations: [CheckedContinuation<Void, Error>] = []
    private var locationContinuations: [CheckedContinuation<OriginLocation, Error>] = []

    public convenience init() {
        self.init(locationManager: CLLocationManagerAdapter())
    }

    init(locationManager: any LocationManaging) {
        self.locationManager = locationManager
    }

    public func requestCurrentLocation() async throws -> OriginLocation {
        switch locationManager.authorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse:
            return try await requestDeviceLocation()
        case .notDetermined:
            try await requestWhenInUseAuthorization()
            return try await requestDeviceLocation()
        case .denied, .restricted:
            throw LocationServiceError.permissionDenied
        @unknown default:
            throw LocationServiceError.permissionDenied
        }
    }

    private func requestWhenInUseAuthorization() async throws {
        try await withCheckedThrowingContinuation { continuation in
            authorizationContinuations.append(continuation)
            guard authorizationContinuations.count == 1 else {
                return
            }

            locationManager.requestWhenInUseAuthorization(onChange: completeAuthorization)
        }
    }

    private func requestDeviceLocation() async throws -> OriginLocation {
        try await withCheckedThrowingContinuation { continuation in
            locationContinuations.append(continuation)
            guard locationContinuations.count == 1 else {
                return
            }

            locationManager.requestLocation(onSuccess: completeLocation, onFailure: completeLocationFailure)
        }
    }

    private func completeAuthorization(with status: CLAuthorizationStatus) {
        guard status != .notDetermined else {
            return
        }

        let continuations = authorizationContinuations
        authorizationContinuations = []

        switch status {
        case .authorizedAlways, .authorizedWhenInUse:
            continuations.forEach { $0.resume() }
        case .denied, .restricted:
            continuations.forEach { $0.resume(throwing: LocationServiceError.permissionDenied) }
        case .notDetermined:
            break
        @unknown default:
            continuations.forEach { $0.resume(throwing: LocationServiceError.permissionDenied) }
        }
    }

    private func completeLocation(with coordinate: CLLocationCoordinate2D) {
        let origin = OriginLocation(name: "현재 위치", coordinate: coordinate, source: .currentDevice)
        let continuations = locationContinuations
        locationContinuations = []
        continuations.forEach { $0.resume(returning: origin) }
    }

    private func completeLocationFailure(with error: Error) {
        let serviceError: LocationServiceError
        if (error as? CLError)?.code == .denied {
            serviceError = .permissionDenied
        } else {
            serviceError = .locationUnavailable
        }

        let continuations = locationContinuations
        locationContinuations = []
        continuations.forEach { $0.resume(throwing: serviceError) }
    }
}

@MainActor
private final class CLLocationManagerAdapter: NSObject, LocationManaging, @MainActor CLLocationManagerDelegate {
    private let manager: CLLocationManager
    private var authorizationChangeHandler: ((CLAuthorizationStatus) -> Void)?
    private var locationSuccessHandler: ((CLLocationCoordinate2D) -> Void)?
    private var locationFailureHandler: ((Error) -> Void)?

    init(manager: CLLocationManager = CLLocationManager()) {
        self.manager = manager
        super.init()
        manager.delegate = self
    }

    var authorizationStatus: CLAuthorizationStatus {
        manager.authorizationStatus
    }

    func requestWhenInUseAuthorization(onChange: @escaping (CLAuthorizationStatus) -> Void) {
        authorizationChangeHandler = onChange
        manager.requestWhenInUseAuthorization()
    }

    func requestLocation(
        onSuccess: @escaping (CLLocationCoordinate2D) -> Void,
        onFailure: @escaping (Error) -> Void
    ) {
        locationSuccessHandler = onSuccess
        locationFailureHandler = onFailure
        manager.requestLocation()
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard manager.authorizationStatus != .notDetermined,
              let handler = authorizationChangeHandler else {
            return
        }

        authorizationChangeHandler = nil
        handler(manager.authorizationStatus)
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let coordinate = locations.last?.coordinate,
              let handler = locationSuccessHandler else {
            return
        }

        locationSuccessHandler = nil
        locationFailureHandler = nil
        handler(coordinate)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        guard let handler = locationFailureHandler else {
            return
        }

        locationSuccessHandler = nil
        locationFailureHandler = nil
        handler(error)
    }
}
