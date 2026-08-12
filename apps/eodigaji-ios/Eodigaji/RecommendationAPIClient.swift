import Foundation

public enum RecommendationAPIError: Error, LocalizedError, Equatable, Sendable {
    case invalidBaseURL
    case invalidResponse
    case transport(message: String)
    case httpStatus(code: Int, body: String?)
    case encoding(message: String)
    case decoding(message: String)

    public var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            return "API 기본 URL이 올바르지 않습니다."
        case .invalidResponse:
            return "API 응답을 이해할 수 없습니다."
        case let .transport(message):
            return "API 연결에 실패했습니다: \(message)"
        case let .httpStatus(code, body):
            if let body, !body.isEmpty {
                return "API가 HTTP \(code)로 응답했습니다: \(body)"
            }
            return "API가 HTTP \(code)로 응답했습니다."
        case let .encoding(message):
            return "API 요청을 만들 수 없습니다: \(message)"
        case let .decoding(message):
            return "API 응답을 해석할 수 없습니다: \(message)"
        }
    }
}

public protocol RecommendationServicing: AnyObject {
    func recommendations(for request: RecommendationRequest) async throws -> RecommendationResponse
}

public protocol RecommendationAPIClientProtocol: RecommendationServicing {
    func health() async throws -> HealthResponse
}

public final class RecommendationAPIClient: RecommendationAPIClientProtocol {
    public static let healthPath = "/healthz"
    public static let recommendationsPath = "/v1/recommendations"

    private let baseURL: URL
    private let session: URLSession

    public init(
        baseURL: URL = DevelopmentConfiguration.apiBaseURL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    public func health() async throws -> HealthResponse {
        try await send(path: Self.healthPath, method: "GET", body: nil)
    }

    public func recommendations(for request: RecommendationRequest) async throws -> RecommendationResponse {
        let body: Data
        do {
            let encoder = JSONEncoder()
            body = try encoder.encode(request)
        } catch {
            throw RecommendationAPIError.encoding(message: error.localizedDescription)
        }

        return try await send(path: Self.recommendationsPath, method: "POST", body: body)
    }

    private func send<Response: Decodable>(
        path: String,
        method: String,
        body: Data?
    ) async throws -> Response {
        guard baseURL.scheme != nil, baseURL.host != nil else {
            throw RecommendationAPIError.invalidBaseURL
        }

        let normalizedPath = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard !normalizedPath.isEmpty else {
            throw RecommendationAPIError.invalidResponse
        }

        var request = URLRequest(url: baseURL.appendingPathComponent(normalizedPath))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        let data: Data
        let urlResponse: URLResponse
        do {
            (data, urlResponse) = try await session.data(for: request)
        } catch let error as RecommendationAPIError {
            throw error
        } catch {
            throw RecommendationAPIError.transport(message: error.localizedDescription)
        }

        guard let response = urlResponse as? HTTPURLResponse else {
            throw RecommendationAPIError.invalidResponse
        }

        guard (200..<300).contains(response.statusCode) else {
            throw RecommendationAPIError.httpStatus(
                code: response.statusCode,
                body: String(data: data, encoding: .utf8)
            )
        }

        do {
            let decoder = JSONDecoder()
            return try decoder.decode(Response.self, from: data)
        } catch {
            throw RecommendationAPIError.decoding(message: error.localizedDescription)
        }
    }
}
