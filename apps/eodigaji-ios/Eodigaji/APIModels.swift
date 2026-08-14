import CoreLocation
import Foundation

public enum TransportMode: String, Codable, CaseIterable, Sendable {
    case publicTransit = "public_transit"
}

public enum MaxTravelTimeMinutes: Int, Codable, CaseIterable, Sendable {
    case twenty = 20
    case thirty = 30
    case forty = 40
    case sixty = 60

    public var recommendationWindowLabel: String {
        let lowerBound = max(0, rawValue - 10)
        return "\(lowerBound)–\(rawValue)분"
    }
}

public enum TimeSlot: String, Codable, CaseIterable, Sendable {
    case morning
    case lunch
    case afternoon
    case evening
    case night
}

public enum Purpose: String, Codable, CaseIterable, Sendable {
    case food
    case cafe
    case date
    case shopping
    case culture
    case rest
}

public enum LiveRouteTransportType: Equatable, Sendable {
    case walking
    case transit
    case automobile
    case other
}

public struct LiveRouteStep: Equatable, Sendable {
    public let instructions: String
    public let distanceMeters: CLLocationDistance
    public let transportType: LiveRouteTransportType

    public init(
        instructions: String,
        distanceMeters: CLLocationDistance,
        transportType: LiveRouteTransportType
    ) {
        self.instructions = instructions
        self.distanceMeters = distanceMeters
        self.transportType = transportType
    }
}

public struct LiveRecommendation: Equatable, Sendable {
    public let placeName: String
    public let address: String
    public let destinationCoordinate: CLLocationCoordinate2D
    public let expectedTravelTime: TimeInterval
    public let distanceMeters: CLLocationDistance
    public let routeSteps: [LiveRouteStep]

    public var journeyTimeMinutes: Int {
        Int(ceil(expectedTravelTime / 60))
    }

    public init(
        placeName: String,
        address: String,
        destinationCoordinate: CLLocationCoordinate2D,
        expectedTravelTime: TimeInterval,
        distanceMeters: CLLocationDistance,
        routeSteps: [LiveRouteStep]
    ) {
        self.placeName = placeName
        self.address = address
        self.destinationCoordinate = destinationCoordinate
        self.expectedTravelTime = expectedTravelTime
        self.distanceMeters = distanceMeters
        self.routeSteps = routeSteps
    }

    public static func == (lhs: LiveRecommendation, rhs: LiveRecommendation) -> Bool {
        lhs.placeName == rhs.placeName
            && lhs.address == rhs.address
            && lhs.destinationCoordinate.latitude == rhs.destinationCoordinate.latitude
            && lhs.destinationCoordinate.longitude == rhs.destinationCoordinate.longitude
            && lhs.expectedTravelTime == rhs.expectedTravelTime
            && lhs.distanceMeters == rhs.distanceMeters
            && lhs.routeSteps == rhs.routeSteps
    }
}

public struct LiveDistrictRecommendation: Equatable, Sendable {
    public let districtName: String
    public let fastestTravelTime: TimeInterval
    public let placeCount: Int
    public let places: [LiveRecommendation]

    public init(
        districtName: String,
        fastestTravelTime: TimeInterval,
        placeCount: Int,
        places: [LiveRecommendation]
    ) {
        self.districtName = districtName
        self.fastestTravelTime = fastestTravelTime
        self.placeCount = placeCount
        self.places = places
    }
}

public struct RecommendationRequest: Codable, Equatable, Sendable {
    public let origin: String
    public let transportMode: TransportMode
    public let maxTravelTimeMinutes: MaxTravelTimeMinutes
    public let timeSlot: TimeSlot
    public let purpose: Purpose

    private enum CodingKeys: String, CodingKey {
        case origin
        case transportMode = "transport_mode"
        case maxTravelTimeMinutes = "max_travel_time_minutes"
        case timeSlot = "time_slot"
        case purpose
    }

    public init(
        origin: String,
        transportMode: TransportMode,
        maxTravelTimeMinutes: MaxTravelTimeMinutes,
        timeSlot: TimeSlot,
        purpose: Purpose
    ) {
        self.origin = origin
        self.transportMode = transportMode
        self.maxTravelTimeMinutes = maxTravelTimeMinutes
        self.timeSlot = timeSlot
        self.purpose = purpose
    }
}

public enum ResultStatus: String, Codable, Sendable {
    case ok
    case noEligibleCandidates = "no_eligible_candidates"
}

public enum RouteStatus: String, Codable, Sendable {
    case availableVerified = "available_verified"
}

public enum CostStatus: String, Codable, Sendable {
    case available
    case unavailable
}

public enum RankingBasis: String, Codable, Sendable {
    case f0PublicRule = "F0-public-rule"
}

public struct Recommendation: Codable, Equatable, Sendable {
    public let id: String
    public let name: String
    public let district: String
    public let journeyTimeMinutes: Int
    public let routeStatus: RouteStatus
    public let costStatus: CostStatus
    public let costWon: Int?
    public let tags: [String]
    public let reason: String
    public let signal: String
    public let method: String
    public let vintage: String

    private enum CodingKeys: String, CodingKey {
        case id
        case name
        case district
        case journeyTimeMinutes = "journey_time_minutes"
        case routeStatus = "route_status"
        case costStatus = "cost_status"
        case costWon = "cost_won"
        case tags
        case reason
        case signal
        case method
        case vintage
    }

    public init(
        id: String,
        name: String,
        district: String,
        journeyTimeMinutes: Int,
        routeStatus: RouteStatus,
        costStatus: CostStatus,
        costWon: Int?,
        tags: [String],
        reason: String,
        signal: String,
        method: String,
        vintage: String
    ) {
        self.id = id
        self.name = name
        self.district = district
        self.journeyTimeMinutes = journeyTimeMinutes
        self.routeStatus = routeStatus
        self.costStatus = costStatus
        self.costWon = costWon
        self.tags = tags
        self.reason = reason
        self.signal = signal
        self.method = method
        self.vintage = vintage
    }
}

public struct RecommendationResponse: Codable, Equatable, Sendable {
    public let resultStatus: ResultStatus
    public let eligibleCount: Int
    public let recommendations: [Recommendation]
    public let rankingBasis: RankingBasis
    public let fixture: Bool
    public let limitations: String

    private enum CodingKeys: String, CodingKey {
        case resultStatus = "result_status"
        case eligibleCount = "eligible_count"
        case recommendations
        case rankingBasis = "ranking_basis"
        case fixture
        case limitations
    }

    public init(
        resultStatus: ResultStatus,
        eligibleCount: Int,
        recommendations: [Recommendation],
        rankingBasis: RankingBasis,
        fixture: Bool,
        limitations: String
    ) {
        self.resultStatus = resultStatus
        self.eligibleCount = eligibleCount
        self.recommendations = recommendations
        self.rankingBasis = rankingBasis
        self.fixture = fixture
        self.limitations = limitations
    }
}

public enum HealthStatus: String, Codable, Sendable {
    case ok
}

public struct KakaoLiveRecommendationRequest: Codable, Sendable {
    public let originName: String
    public let originLatitude: CLLocationDegrees
    public let originLongitude: CLLocationDegrees
    public let purpose: Purpose
    public let maxTravelTimeMinutes: MaxTravelTimeMinutes

    private enum CodingKeys: String, CodingKey {
        case originName = "origin_name"
        case originLatitude = "origin_latitude"
        case originLongitude = "origin_longitude"
        case purpose
        case maxTravelTimeMinutes = "max_travel_time_minutes"
    }

    public init(origin: OriginLocation, purpose: Purpose, maxTravelTime: MaxTravelTimeMinutes) {
        originName = origin.name
        originLatitude = origin.coordinate.latitude
        originLongitude = origin.coordinate.longitude
        self.purpose = purpose
        maxTravelTimeMinutes = maxTravelTime
    }
}

struct KakaoLiveRecommendationResponse: Decodable {
    let recommendations: [KakaoLiveRecommendation]
}

struct KakaoLiveRecommendation: Decodable {
    let placeName: String
    let address: String
    let destinationLatitude: CLLocationDegrees
    let destinationLongitude: CLLocationDegrees
    let expectedTravelTimeSeconds: TimeInterval
    let distanceMeters: CLLocationDistance
    let routeSteps: [KakaoLiveRouteStep]

    private enum CodingKeys: String, CodingKey {
        case placeName = "place_name"
        case address
        case destinationLatitude = "destination_latitude"
        case destinationLongitude = "destination_longitude"
        case expectedTravelTimeSeconds = "expected_travel_time_seconds"
        case distanceMeters = "distance_meters"
        case routeSteps = "route_steps"
    }

    func asLiveRecommendation() -> LiveRecommendation {
        LiveRecommendation(
            placeName: placeName,
            address: address,
            destinationCoordinate: CLLocationCoordinate2D(latitude: destinationLatitude, longitude: destinationLongitude),
            expectedTravelTime: expectedTravelTimeSeconds,
            distanceMeters: distanceMeters,
            routeSteps: routeSteps.map(\.asLiveRouteStep)
        )
    }
}

struct KakaoLiveDistrictRecommendationResponse: Decodable {
    let districts: [KakaoLiveDistrictRecommendation]
}

struct KakaoLiveDistrictRecommendation: Decodable {
    let districtName: String
    let fastestTravelTimeSeconds: TimeInterval
    let placeCount: Int
    let places: [KakaoLiveRecommendation]

    private enum CodingKeys: String, CodingKey {
        case districtName = "district_name"
        case fastestTravelTimeSeconds = "fastest_travel_time_seconds"
        case placeCount = "place_count"
        case places
    }

    func asLiveDistrictRecommendation() -> LiveDistrictRecommendation {
        LiveDistrictRecommendation(
            districtName: districtName,
            fastestTravelTime: fastestTravelTimeSeconds,
            placeCount: placeCount,
            places: places.map { $0.asLiveRecommendation() }
        )
    }
}

struct KakaoLiveRouteStep: Decodable {
    let instruction: String
    let distanceMeters: CLLocationDistance
    let transportMode: String

    private enum CodingKeys: String, CodingKey {
        case instruction
        case distanceMeters = "distance_meters"
        case transportMode = "transport_mode"
    }

    var asLiveRouteStep: LiveRouteStep {
        let type: LiveRouteTransportType
        switch transportMode {
        case "walking": type = .walking
        case "transit": type = .transit
        case "automobile": type = .automobile
        default: type = .other
        }
        return LiveRouteStep(instructions: instruction, distanceMeters: distanceMeters, transportType: type)
    }
}

public struct HealthResponse: Codable, Equatable, Sendable {
    public let status: HealthStatus
    public let fixture: Bool

    private enum CodingKeys: String, CodingKey {
        case status
        case fixture
    }

    public init(status: HealthStatus, fixture: Bool) {
        self.status = status
        self.fixture = fixture
    }
}
