import Combine
import Foundation
import MapKit

public enum LiveRecommendationViewModelError: Error, Equatable, LocalizedError {
    case originRequired

    public var errorDescription: String? {
        switch self {
        case .originRequired:
            return "현재 위치, 장소 검색 또는 지도 핀으로 출발지를 선택해 주세요."
        }
    }
}

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
    @Published public private(set) var shouldShowResults = false
    @Published public private(set) var selectedOrigin: OriginLocation?
    @Published public private(set) var liveResults: [LiveRecommendation] = []
    @Published public private(set) var liveDistricts: [LiveDistrictRecommendation] = []
    @Published public private(set) var selectedDistrict: LiveDistrictRecommendation?
    @Published public private(set) var liveError: Error?
    @Published public private(set) var liveResultsOrigin: OriginLocation?
    @Published public private(set) var liveResultsMaxTravelTime: MaxTravelTimeMinutes?
    @Published public var originQuery = "" {
        didSet {
            originSearchGeneration += 1
        }
    }
    @Published public private(set) var originSearchResults: [OriginLocation] = []
    @Published public private(set) var originError: Error?
    @Published public private(set) var originSearchError: Error?
    @Published public private(set) var isResolvingOrigin = false
    @Published public private(set) var isSearchingOrigins = false
    @Published public private(set) var hasCompletedOriginSearch = false
    @Published public private(set) var lastUpdatedAt: Date?

    private let service: (any RecommendationServicing)?
    private let liveService: (any LiveRecommendationServicing)?
    private let districtService: (any DistrictRecommendationServicing)?
    private let locationService: (any LocationServicing)?
    private let originSearchService: (any OriginSearching)?
    private var didRequestInitialOrigin = false
    private var originSelectionGeneration = 0
    private var originSearchGeneration = 0

    public init(
        service: any RecommendationServicing,
        origin: String = "회기역",
        transportMode: TransportMode = .publicTransit,
        maxTravelTimeMinutes: MaxTravelTimeMinutes = .thirty,
        timeSlot: TimeSlot = .evening,
        purpose: Purpose = .food
    ) {
        self.service = service
        liveService = nil
        districtService = nil
        locationService = nil
        originSearchService = nil
        self.origin = origin
        self.transportMode = transportMode
        self.maxTravelTimeMinutes = maxTravelTimeMinutes
        self.timeSlot = timeSlot
        self.purpose = purpose
    }

    public init(
        liveService: any LiveRecommendationServicing,
        locationService: (any LocationServicing)? = nil,
        originSearchService: (any OriginSearching)? = nil,
        selectedOrigin: OriginLocation? = nil,
        maxTravelTimeMinutes: MaxTravelTimeMinutes = .thirty,
        purpose: Purpose = .food
    ) {
        service = nil
        self.liveService = liveService
        districtService = nil
        self.locationService = locationService ?? LocationService()
        self.originSearchService = originSearchService ?? OriginSearchService()
        origin = selectedOrigin?.name ?? ""
        transportMode = .publicTransit
        self.maxTravelTimeMinutes = maxTravelTimeMinutes
        timeSlot = .evening
        self.purpose = purpose
        self.selectedOrigin = selectedOrigin
    }

    public init(
        districtService: any DistrictRecommendationServicing,
        locationService: (any LocationServicing)? = nil,
        originSearchService: (any OriginSearching)? = nil,
        selectedOrigin: OriginLocation? = nil,
        maxTravelTimeMinutes: MaxTravelTimeMinutes = .thirty,
        purpose: Purpose = .food
    ) {
        service = nil
        liveService = nil
        self.districtService = districtService
        self.locationService = locationService ?? LocationService()
        self.originSearchService = originSearchService ?? OriginSearchService()
        origin = selectedOrigin?.name ?? ""
        transportMode = .publicTransit
        self.maxTravelTimeMinutes = maxTravelTimeMinutes
        timeSlot = .evening
        self.purpose = purpose
        self.selectedOrigin = selectedOrigin
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
        guard !isLoading, let service else {
            return
        }

        isLoading = true
        error = nil
        response = nil
        shouldShowResults = false

        defer {
            isLoading = false
        }

        do {
            response = try await service.recommendations(for: currentRequest)
            shouldShowResults = true
        } catch {
            self.error = error
        }
    }

    public func retry() async {
        await recommend()
    }

    public func selectOrigin(_ origin: OriginLocation) {
        originSelectionGeneration += 1
        selectedOrigin = origin
        self.origin = origin.name
        originQuery = origin.name
        originError = nil
        originSearchError = nil
    }

    public func requestInitialCurrentLocation() async {
        guard !didRequestInitialOrigin, selectedOrigin == nil else {
            return
        }

        didRequestInitialOrigin = true
        await requestCurrentLocation()
    }

    public func requestCurrentLocation() async {
        guard !isResolvingOrigin, let locationService else {
            return
        }

        isResolvingOrigin = true
        originError = nil
        let requestGeneration = originSelectionGeneration

        defer {
            isResolvingOrigin = false
        }

        do {
            let origin = try await locationService.requestCurrentLocation()
            guard requestGeneration == originSelectionGeneration else { return }
            selectOrigin(origin)
        } catch {
            guard requestGeneration == originSelectionGeneration else { return }
            originError = error
        }
    }

    public func searchOrigins() async {
        let query = originQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty, !isSearchingOrigins, let originSearchService else {
            return
        }

        isSearchingOrigins = true
        hasCompletedOriginSearch = false
        originSearchError = nil
        originSearchResults = []
        let requestGeneration = originSearchGeneration

        defer {
            isSearchingOrigins = false
        }

        let region = selectedOrigin.map {
            MKCoordinateRegion(
                center: $0.coordinate,
                span: MKCoordinateSpan(latitudeDelta: 0.2, longitudeDelta: 0.2)
            )
        }

        do {
            let results = try await originSearchService.search(query: query, region: region)
            guard requestGeneration == originSearchGeneration else { return }
            originSearchResults = results
            hasCompletedOriginSearch = true
        } catch {
            guard requestGeneration == originSearchGeneration else { return }
            originSearchError = error
        }
    }

    public func recommendLive() async {
        guard !isLoading,
              let liveService else {
            return
        }

        guard let selectedOrigin else {
            liveError = LiveRecommendationViewModelError.originRequired
            return
        }
        let requestedOrigin = selectedOrigin
        let requestedMaxTravelTime = maxTravelTimeMinutes
        let requestedPurpose = purpose

        isLoading = true
        liveError = nil
        liveResults = []
        liveResultsOrigin = nil
        liveResultsMaxTravelTime = nil
        shouldShowResults = false

        defer {
            isLoading = false
        }

        do {
            liveResults = try await liveService.recommend(
                from: requestedOrigin,
                purpose: requestedPurpose,
                maxTravelTime: requestedMaxTravelTime
            )
            liveResultsOrigin = requestedOrigin
            liveResultsMaxTravelTime = requestedMaxTravelTime
            lastUpdatedAt = Date()
            shouldShowResults = true
        } catch {
            liveError = error
        }
    }

    public func retryLive() async {
        await recommendLive()
    }

    public func recommendDistrictsLive() async {
        guard !isLoading,
              let districtService else {
            return
        }

        guard let selectedOrigin else {
            liveError = LiveRecommendationViewModelError.originRequired
            return
        }
        let requestedOrigin = selectedOrigin
        let requestedMaxTravelTime = maxTravelTimeMinutes
        let requestedPurpose = purpose

        isLoading = true
        liveError = nil
        liveResults = []
        liveDistricts = []
        selectedDistrict = nil
        liveResultsOrigin = nil
        liveResultsMaxTravelTime = nil
        shouldShowResults = false

        defer {
            isLoading = false
        }

        do {
            liveDistricts = try await districtService.recommendDistricts(
                from: requestedOrigin,
                purpose: requestedPurpose,
                maxTravelTime: requestedMaxTravelTime
            )
            liveResultsOrigin = requestedOrigin
            liveResultsMaxTravelTime = requestedMaxTravelTime
            lastUpdatedAt = Date()
            shouldShowResults = true
        } catch {
            liveError = error
        }
    }

    public func selectDistrict(_ district: LiveDistrictRecommendation) {
        selectedDistrict = district
    }

    public func dismissDistrictPlaces() {
        selectedDistrict = nil
    }

    public var originErrorMessage: String? {
        guard let originError else { return nil }

        if originError as? LocationServiceError == .permissionDenied {
            return "현재 위치 권한이 없습니다. 장소를 검색하거나 지도에서 핀을 선택해 주세요."
        }

        return localizedMessage(
            for: originError,
            fallback: "현재 위치를 가져오지 못했습니다. 장소 검색이나 지도 핀을 이용해 주세요."
        )
    }

    public var originSearchErrorMessage: String? {
        originSearchError.map {
            localizedMessage(for: $0, fallback: "장소 검색에 실패했습니다. 검색어를 확인하고 다시 시도해 주세요.")
        }
    }

    public var liveErrorMessage: String? {
        liveError.map {
            localizedMessage(for: $0, fallback: "실시간 경로를 불러오지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요.")
        }
    }

    public func dismissResults() {
        shouldShowResults = false
    }

    private func localizedMessage(for error: Error, fallback: String) -> String {
        if let localizedError = error as? LocalizedError,
           let description = localizedError.errorDescription,
           !description.isEmpty {
            return description
        }

        return fallback
    }
}
