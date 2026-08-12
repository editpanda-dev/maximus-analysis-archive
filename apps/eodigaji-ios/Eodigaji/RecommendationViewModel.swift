import Combine
import Foundation

@MainActor
public final class RecommendationViewModel: ObservableObject {
    @Published public var origin: String
    @Published public var transportMode: TransportMode
    @Published public var maxTravelTimeMinutes: MaxTravelTimeMinutes
    @Published public var timeSlot: TimeSlot
    @Published public var purpose: Purpose

    @Published public private(set) var isLoading = false
    @Published public private(set) var response: RecommendationResponse?
    @Published public private(set) var error: Error?

    private let service: any RecommendationServicing

    public init(
        service: any RecommendationServicing,
        origin: String = "회기역",
        transportMode: TransportMode = .publicTransit,
        maxTravelTimeMinutes: MaxTravelTimeMinutes = .thirty,
        timeSlot: TimeSlot = .evening,
        purpose: Purpose = .food
    ) {
        self.service = service
        self.origin = origin
        self.transportMode = transportMode
        self.maxTravelTimeMinutes = maxTravelTimeMinutes
        self.timeSlot = timeSlot
        self.purpose = purpose
    }

    public var currentRequest: RecommendationRequest {
        RecommendationRequest(
            origin: origin,
            transportMode: transportMode,
            maxTravelTimeMinutes: maxTravelTimeMinutes,
            timeSlot: timeSlot,
            purpose: purpose
        )
    }

    public var errorMessage: String? {
        guard let error else {
            return nil
        }

        if let localizedError = error as? LocalizedError,
           let description = localizedError.errorDescription,
           !description.isEmpty {
            return "추천을 불러오지 못했습니다. \(description)"
        }

        return "추천을 불러오지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요."
    }

    public func recommend() async {
        guard !isLoading else {
            return
        }

        isLoading = true
        error = nil
        response = nil

        defer {
            isLoading = false
        }

        do {
            response = try await service.recommendations(for: currentRequest)
        } catch {
            self.error = error
        }
    }

    public func retry() async {
        await recommend()
    }
}
