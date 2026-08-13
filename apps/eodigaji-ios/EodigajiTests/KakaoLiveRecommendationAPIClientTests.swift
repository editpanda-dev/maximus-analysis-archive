import Foundation
import XCTest
@testable import Eodigaji

@MainActor
final class KakaoLiveRecommendationAPIClientTests: XCTestCase {
    override func tearDown() {
        KakaoURLProtocolStub.requestHandler = nil
        KakaoURLProtocolStub.lastRequest = nil
        super.tearDown()
    }

    func testRecommendPostsSnakeCaseCoordinatesAndMapsRouteCards() async throws {
        let session = stubbedSession()
        let responseData = Data(
            """
            {
              "result_status": "ok",
              "provider": "kakao",
              "queried_at": "2026-08-13T12:00:00Z",
              "eligible_count": 1,
              "recommendations": [{
                "place_name": "서울숲 카페",
                "address": "서울 성동구 뚝섬로 273",
                "destination_latitude": 37.5444,
                "destination_longitude": 127.0374,
                "expected_travel_time_seconds": 1800,
                "distance_meters": 4200,
                "route_steps": [{
                  "instruction": "정류장까지 도보",
                  "distance_meters": 200,
                  "duration_seconds": 180,
                  "transport_mode": "walking"
                }, {
                  "instruction": "2호선 탑승",
                  "distance_meters": 4000,
                  "duration_seconds": 1620,
                  "transport_mode": "transit"
                }]
              }],
              "fixture": false,
              "limitations": "카카오 제공 경로만 사용합니다."
            }
            """.utf8
        )
        KakaoURLProtocolStub.requestHandler = { request in
            KakaoURLProtocolStub.lastRequest = request
            return (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, responseData)
        }
        let client = KakaoLiveRecommendationAPIClient(
            baseURL: URL(string: "http://127.0.0.1:8000")!,
            session: session
        )
        let origin = OriginLocation(
            name: "모현 한국외대",
            coordinate: .init(latitude: 37.3389, longitude: 127.2697),
            source: .searchedPlace
        )

        let recommendations = try await client.recommend(
            from: origin,
            purpose: .cafe,
            maxTravelTime: .thirty
        )

        XCTAssertEqual(KakaoURLProtocolStub.lastRequest?.httpMethod, "POST")
        XCTAssertEqual(KakaoURLProtocolStub.lastRequest?.url?.path, "/v1/live-recommendations")
        let body = try XCTUnwrap(KakaoURLProtocolStub.lastRequest?.httpBody)
        let json = try XCTUnwrap(try JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["origin_name"] as? String, "모현 한국외대")
        XCTAssertEqual(try XCTUnwrap(json["origin_latitude"] as? Double), 37.3389, accuracy: 0.000001)
        XCTAssertEqual(try XCTUnwrap(json["origin_longitude"] as? Double), 127.2697, accuracy: 0.000001)
        XCTAssertNil(json["originLatitude"])
        XCTAssertNil(json["originLongitude"])
        XCTAssertEqual(recommendations.count, 1)
        XCTAssertEqual(recommendations[0].placeName, "서울숲 카페")
        XCTAssertEqual(recommendations[0].expectedTravelTime, 1800)
        XCTAssertEqual(recommendations[0].distanceMeters, 4200)
        XCTAssertEqual(recommendations[0].routeSteps.map(\.transportType), [LiveRouteTransportType.walking, .transit])
    }

    func testBackendValidationAndProviderFailuresExposeSafeMessageWithoutFallback() async throws {
        let session = stubbedSession()
        let client = KakaoLiveRecommendationAPIClient(
            baseURL: URL(string: "http://127.0.0.1:8000")!,
            session: session
        )
        let origin = OriginLocation(
            name: "잘못된 핀",
            coordinate: .init(latitude: 40.7128, longitude: -74.006),
            source: .mapPin
        )

        for (status, detail) in [(422, "origin coordinates must be within supported South Korea regions"), (503, "Live recommendations are temporarily unavailable.")] {
            KakaoURLProtocolStub.requestHandler = { request in
                let data = Data("{\"detail\":\"\(detail)\"}".utf8)
                return (HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!, data)
            }

            do {
                _ = try await client.recommend(from: origin, purpose: .cafe, maxTravelTime: .thirty)
                XCTFail("Expected backend error")
            } catch let error as KakaoLiveRecommendationAPIError {
                XCTAssertEqual(error.statusCode, status)
                XCTAssertEqual(error.errorDescription, detail)
            }
        }
    }

    private func stubbedSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [KakaoURLProtocolStub.self]
        return URLSession(configuration: configuration)
    }
}

private final class KakaoURLProtocolStub: URLProtocol {
    static var requestHandler: ((URLRequest) -> (HTTPURLResponse, Data))?
    static var lastRequest: URLRequest?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let requestHandler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        let (response, data) = requestHandler(request)
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
