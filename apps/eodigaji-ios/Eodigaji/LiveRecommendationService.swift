import CoreLocation
import Foundation
import MapKit

@MainActor
public protocol LiveRecommendationServicing: AnyObject {
    func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation]
}

struct LivePlaceSearchRequest {
    let query: String
    let region: MKCoordinateRegion
}

struct LivePlaceCandidate {
    let name: String
    let address: String
    let coordinate: CLLocationCoordinate2D
}

struct LiveDirectionsRequest {
    let source: CLLocationCoordinate2D
    let destination: CLLocationCoordinate2D
    let transportType: MKDirectionsTransportType
}

struct LiveTransitRoute: Equatable {
    let expectedTravelTime: TimeInterval
    let distanceMeters: CLLocationDistance
    let steps: [LiveRouteStep]
}

@MainActor
protocol LivePlaceSearchPort: AnyObject {
    func search(_ request: LivePlaceSearchRequest) async throws -> [LivePlaceCandidate]
}

@MainActor
protocol LiveDirectionsPort: AnyObject {
    func route(for request: LiveDirectionsRequest) async throws -> LiveTransitRoute?
}

@MainActor
public final class LiveRecommendationService: LiveRecommendationServicing {
    private let searchPort: any LivePlaceSearchPort
    private let directionsPort: any LiveDirectionsPort

    public convenience init() {
        self.init(
            searchPort: MapKitLivePlaceSearchPort(),
            directionsPort: MapKitLiveDirectionsPort()
        )
    }

    init(searchPort: any LivePlaceSearchPort, directionsPort: any LiveDirectionsPort) {
        self.searchPort = searchPort
        self.directionsPort = directionsPort
    }

    public func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation] {
        let candidates = try await searchPort.search(
            LivePlaceSearchRequest(
                query: purpose.searchQuery,
                region: MKCoordinateRegion(
                    center: origin.coordinate,
                    latitudinalMeters: 10_000,
                    longitudinalMeters: 10_000
                )
            )
        )
        let maximumTravelTime = TimeInterval(maxTravelTime.rawValue * 60)
        var eligible: [(offset: Int, recommendation: LiveRecommendation)] = []

        for (offset, candidate) in candidates.enumerated() {
            let route = try await directionsPort.route(
                for: LiveDirectionsRequest(
                    source: origin.coordinate,
                    destination: candidate.coordinate,
                    transportType: .transit
                )
            )

            guard let route, route.expectedTravelTime <= maximumTravelTime else {
                continue
            }

            eligible.append(
                (
                    offset: offset,
                    recommendation: LiveRecommendation(
                        placeName: candidate.name,
                        address: candidate.address,
                        destinationCoordinate: candidate.coordinate,
                        expectedTravelTime: route.expectedTravelTime,
                        distanceMeters: route.distanceMeters,
                        routeSteps: route.steps
                    )
                )
            )
        }

        return eligible.sorted { lhs, rhs in
            if lhs.recommendation.expectedTravelTime != rhs.recommendation.expectedTravelTime {
                return lhs.recommendation.expectedTravelTime < rhs.recommendation.expectedTravelTime
            }
            if lhs.recommendation.placeName != rhs.recommendation.placeName {
                return lhs.recommendation.placeName < rhs.recommendation.placeName
            }
            return lhs.offset < rhs.offset
        }.map(\.recommendation)
    }
}

@MainActor
private final class MapKitLivePlaceSearchPort: LivePlaceSearchPort {
    func search(_ request: LivePlaceSearchRequest) async throws -> [LivePlaceCandidate] {
        let mapRequest = MKLocalSearch.Request()
        mapRequest.naturalLanguageQuery = request.query
        mapRequest.region = request.region

        return try await MKLocalSearch(request: mapRequest).start().mapItems.compactMap { mapItem in
            let name = mapItem.name?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            guard !name.isEmpty else { return nil }

            return LivePlaceCandidate(
                name: name,
                address: mapItem.placemark.title ?? "",
                coordinate: mapItem.placemark.coordinate
            )
        }
    }
}

@MainActor
private final class MapKitLiveDirectionsPort: LiveDirectionsPort {
    func route(for request: LiveDirectionsRequest) async throws -> LiveTransitRoute? {
        let directionsRequest = MKDirections.Request()
        directionsRequest.source = MKMapItem(
            placemark: MKPlacemark(coordinate: request.source)
        )
        directionsRequest.destination = MKMapItem(
            placemark: MKPlacemark(coordinate: request.destination)
        )
        directionsRequest.transportType = request.transportType

        do {
            let response = try await MKDirections(request: directionsRequest).calculate()
            guard let route = response.routes.min(by: {
                $0.expectedTravelTime < $1.expectedTravelTime
            }) else {
                return nil
            }

            return LiveTransitRoute(
                expectedTravelTime: route.expectedTravelTime,
                distanceMeters: route.distance,
                steps: route.steps.compactMap(Self.convert)
            )
        } catch let error as MKError where error.code == .directionsNotFound {
            return nil
        }
    }

    private static func convert(_ step: MKRoute.Step) -> LiveRouteStep? {
        let instructions = step.instructions.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !instructions.isEmpty else { return nil }

        return LiveRouteStep(
            instructions: instructions,
            distanceMeters: step.distance,
            transportType: convert(step.transportType)
        )
    }

    private static func convert(_ transportType: MKDirectionsTransportType) -> LiveRouteTransportType {
        if transportType == .walking {
            return .walking
        }
        if transportType == .transit {
            return .transit
        }
        if transportType == .automobile {
            return .automobile
        }
        return .other
    }
}

private extension Purpose {
    var searchQuery: String {
        switch self {
        case .food:
            return "맛집"
        case .cafe:
            return "카페"
        case .date:
            return "데이트"
        case .shopping:
            return "쇼핑"
        case .culture:
            return "문화"
        case .rest:
            return "휴식"
        }
    }
}
