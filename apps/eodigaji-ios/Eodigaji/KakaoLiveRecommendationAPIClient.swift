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

    static func backendMessage(from data: Data, statusCode: Int) -> String {
        if let envelope = try? JSONDecoder().decode(BackendErrorEnvelope.self, from: data),
           let message = envelope.userFacingMessage {
            return message
        }
        return "실시간 추천 요청이 실패했습니다. (HTTP \(statusCode))"
    }
}

@MainActor
public protocol LiveRecommendationServicing: AnyObject {
    func recommend(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveRecommendation]
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
                message: KakaoLiveRecommendationAPIError.backendMessage(from: data, statusCode: httpResponse.statusCode)
            )
        }
        do {
            return try JSONDecoder().decode(KakaoLiveRecommendationResponse.self, from: data)
                .recommendations.map { $0.asLiveRecommendation() }
        } catch {
            throw KakaoLiveRecommendationAPIError.decoding(message: error.localizedDescription)
        }
    }

}

private struct BackendErrorEnvelope: Decodable {
    let detail: Detail

    enum Detail: Decodable {
        case message(String)
        case validation([ValidationIssue])

        init(from decoder: Decoder) throws {
            let container = try decoder.singleValueContainer()
            if let message = try? container.decode(String.self) {
                self = .message(message)
            } else {
                self = .validation(try container.decode([ValidationIssue].self))
            }
        }
    }

    struct ValidationIssue: Decodable {
        let type: String
        let loc: [String]
        let msg: String
    }

    var userFacingMessage: String? {
        switch detail {
        case let .message(message):
            return message.isEmpty ? nil : message
        case let .validation(issues):
            guard !issues.isEmpty else { return nil }
            if issues.contains(where: { $0.msg.contains("origin coordinates must be within supported South Korea regions") }) ||
                issues.contains(where: {
                    ["less_than_equal", "greater_than_equal"].contains($0.type) &&
                        ($0.loc.contains("origin_latitude") || $0.loc.contains("origin_longitude"))
                }) {
                return "출발 좌표가 대한민국 지원 지역 밖입니다. 지도에서 국내 출발지를 선택해 주세요."
            }
            return "요청 내용을 확인한 뒤 다시 시도해 주세요."
        }
    }
}
