import Foundation

public enum TransportMode: String, Codable, CaseIterable, Sendable {
    case publicTransit = "public_transit"
}

public enum MaxTravelTimeMinutes: Int, Codable, CaseIterable, Sendable {
    case twenty = 20
    case thirty = 30
    case forty = 40
    case sixty = 60
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
