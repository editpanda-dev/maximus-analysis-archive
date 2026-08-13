import Foundation

@MainActor
public protocol DistrictRecommendationServicing: AnyObject {
    func recommendDistricts(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveDistrictRecommendation]
}

@MainActor
public final class KakaoDistrictRecommendationAPIClient: DistrictRecommendationServicing {
    public static let recommendationsPath = "/v1/live-district-recommendations"

    private let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL = DevelopmentConfiguration.apiBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    public func recommendDistricts(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveDistrictRecommendation] {
        guard baseURL.scheme != nil, baseURL.host != nil else {
            throw KakaoLiveRecommendationAPIError.invalidBaseURL
        }
        let body: Data
        do {
            body = try JSONEncoder().encode(
                KakaoLiveRecommendationRequest(origin: origin, purpose: purpose, maxTravelTime: maxTravelTime)
            )
        } catch {
            throw KakaoLiveRecommendationAPIError.encoding(message: error.localizedDescription)
        }
        var request = URLRequest(
            url: baseURL.appendingPathComponent(
                Self.recommendationsPath.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            )
        )
        request.httpMethod = "POST"
        request.httpBody = body
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw KakaoLiveRecommendationAPIError.transport(message: error.localizedDescription)
        }
        guard let httpResponse = response as? HTTPURLResponse else {
            throw KakaoLiveRecommendationAPIError.transport(message: "HTTP 응답이 아닙니다.")
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            throw KakaoLiveRecommendationAPIError.backend(
                statusCode: httpResponse.statusCode,
                message: KakaoLiveRecommendationAPIError.backendMessage(
                    from: data,
                    statusCode: httpResponse.statusCode
                )
            )
        }
        do {
            return try JSONDecoder().decode(KakaoLiveDistrictRecommendationResponse.self, from: data)
                .districts.map { $0.asLiveDistrictRecommendation() }
        } catch {
            throw KakaoLiveRecommendationAPIError.decoding(message: error.localizedDescription)
        }
    }
}
