import Foundation

public enum KakaoLiveRecommendationAPIError: Error, Equatable, LocalizedError, Sendable {
    case invalidBaseURL
    case transport(message: String)
    case encoding(message: String)
    case decoding(message: String)
    case backend(statusCode: Int, message: String)

    public var statusCode: Int? {
        guard case let .backend(statusCode, _) = self else { return nil }
        return statusCode
    }

    public var errorDescription: String? {
        switch self {
        case .invalidBaseURL: return "API 기본 URL이 올바르지 않습니다."
        case let .transport(message): return "API 연결에 실패했습니다: \(message)"
        case let .encoding(message): return "API 요청을 만들 수 없습니다: \(message)"
        case let .decoding(message): return "API 응답을 해석할 수 없습니다: \(message)"
        case let .backend(_, message): return message
        }
    }
}

@MainActor
public protocol KakaoLiveRecommendationServicing: LiveRecommendationServicing {}

@MainActor
public final class KakaoLiveRecommendationAPIClient: KakaoLiveRecommendationServicing {
    public static let recommendationsPath = "/v1/live-recommendations"

    private let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL = DevelopmentConfiguration.apiBaseURL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    public func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation] {
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
        var request = URLRequest(url: baseURL.appendingPathComponent(Self.recommendationsPath.trimmingCharacters(in: CharacterSet(charactersIn: "/"))))
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
                message: Self.backendMessage(from: data, statusCode: httpResponse.statusCode)
            )
        }
        do {
            return try JSONDecoder().decode(KakaoLiveRecommendationResponse.self, from: data)
                .recommendations.map { $0.asLiveRecommendation() }
        } catch {
            throw KakaoLiveRecommendationAPIError.decoding(message: error.localizedDescription)
        }
    }

    private static func backendMessage(from data: Data, statusCode: Int) -> String {
        if let envelope = try? JSONDecoder().decode(BackendErrorEnvelope.self, from: data),
           !envelope.detail.isEmpty {
            return envelope.detail
        }
        return "실시간 추천 요청이 실패했습니다. (HTTP \(statusCode))"
    }
}

private struct BackendErrorEnvelope: Decodable {
    let detail: String
}
