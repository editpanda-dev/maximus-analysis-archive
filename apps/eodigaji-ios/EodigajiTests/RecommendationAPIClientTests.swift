import Foundation
import XCTest
@testable import Eodigaji

final class RecommendationAPIClientTests: XCTestCase {
    override func tearDown() {
        URLProtocolStub.requestHandler = nil
        super.tearDown()
    }

    func testRecommendationsPostsToConfiguredEndpointAndDecodesResponse() async throws {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [URLProtocolStub.self]
        let session = URLSession(configuration: configuration)
        let responseData = Data(
            """
            {
              "result_status": "no_eligible_candidates",
              "eligible_count": 0,
              "recommendations": [],
              "ranking_basis": "F0-public-rule",
              "fixture": true,
              "limitations": "데모 fixture"
            }
            """.utf8
        )
        URLProtocolStub.requestHandler = { request in
            URLProtocolStub.lastRequest = request
            return (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, responseData)
        }

        let client = RecommendationAPIClient(
            baseURL: URL(string: "http://127.0.0.1:8000")!,
            session: session
        )
        let response = try await client.recommendations(for: Self.sampleRequest)

        XCTAssertEqual(URLProtocolStub.lastRequest?.httpMethod, "POST")
        XCTAssertEqual(URLProtocolStub.lastRequest?.url?.path, "/v1/recommendations")
        XCTAssertEqual(response.resultStatus, .noEligibleCandidates)
        XCTAssertTrue(response.fixture)
    }

    func testHealthUsesHealthzEndpoint() async throws {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [URLProtocolStub.self]
        let session = URLSession(configuration: configuration)
        URLProtocolStub.requestHandler = { request in
            URLProtocolStub.lastRequest = request
            let data = Data("{\"status\":\"ok\",\"fixture\":true}".utf8)
            return (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, data)
        }

        let client = RecommendationAPIClient(
            baseURL: URL(string: "http://127.0.0.1:8000")!,
            session: session
        )
        let response = try await client.health()

        XCTAssertEqual(URLProtocolStub.lastRequest?.httpMethod, "GET")
        XCTAssertEqual(URLProtocolStub.lastRequest?.url?.path, "/healthz")
        XCTAssertEqual(response.status, .ok)
        XCTAssertTrue(response.fixture)
    }

    func testNonSuccessResponseThrowsTypedHTTPError() async throws {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [URLProtocolStub.self]
        let session = URLSession(configuration: configuration)
        URLProtocolStub.requestHandler = { request in
            let data = Data("{\"detail\":\"invalid input\"}".utf8)
            return (HTTPURLResponse(url: request.url!, statusCode: 422, httpVersion: nil, headerFields: nil)!, data)
        }

        let client = RecommendationAPIClient(
            baseURL: URL(string: "http://127.0.0.1:8000")!,
            session: session
        )

        do {
            _ = try await client.health()
            XCTFail("Expected a typed HTTP error")
        } catch let error as RecommendationAPIError {
            guard case let .httpStatus(code, body) = error else {
                return XCTFail("Expected httpStatus, got \(error)")
            }
            XCTAssertEqual(code, 422)
            XCTAssertEqual(body, "{\"detail\":\"invalid input\"}")
        }
    }

    private static let sampleRequest = RecommendationRequest(
        origin: "회기역",
        transportMode: .publicTransit,
        maxTravelTimeMinutes: .thirty,
        timeSlot: .evening,
        purpose: .food
    )
}

private final class URLProtocolStub: URLProtocol {
    static var requestHandler: ((URLRequest) -> (HTTPURLResponse, Data))?
    static var lastRequest: URLRequest?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let requestHandler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: RecommendationAPIError.invalidResponse)
            return
        }

        let (response, data) = requestHandler(request)
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
