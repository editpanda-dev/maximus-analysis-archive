import Foundation
import XCTest
@testable import Eodigaji

@MainActor
final class KakaoLiveRecommendationAPIClientTests: XCTestCase {
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
        KakaoURLProtocolStub.register(host: "success.test") { request in
            KakaoURLProtocolStub.lastRequest = request
            KakaoURLProtocolStub.lastBody = KakaoURLProtocolStub.body(of: request)
            return (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, responseData)
        }
        let client = KakaoLiveRecommendationAPIClient(
            baseURL: URL(string: "http://success.test")!,
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
        let body = try XCTUnwrap(KakaoURLProtocolStub.lastBody)
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

    func testFastAPIValidationDetailArrayProvidesKoreanOriginGuidanceWithoutFallback() async throws {
        let session = stubbedSession()
        let client = KakaoLiveRecommendationAPIClient(
            baseURL: URL(string: "http://validation.test")!,
            session: session
        )
        let origin = OriginLocation(
            name: "잘못된 핀",
            coordinate: .init(latitude: 40.7128, longitude: -74.006),
            source: .mapPin
        )

        KakaoURLProtocolStub.register(host: "validation.test") { request in
            let data = Data(
                """
                {"detail":[{"type":"value_error","loc":["body"],"msg":"Value error, origin coordinates must be within supported South Korea regions","input":{"origin_name":"잘못된 핀","origin_latitude":40.7128,"origin_longitude":-74.006,"purpose":"cafe","max_travel_time_minutes":30},"ctx":{"error":{}}}]}
                """.utf8
            )
            return (HTTPURLResponse(url: request.url!, statusCode: 422, httpVersion: nil, headerFields: nil)!, data)
        }

        do {
            _ = try await client.recommend(from: origin, purpose: .cafe, maxTravelTime: .thirty)
            XCTFail("Expected backend error")
        } catch let error as KakaoLiveRecommendationAPIError {
            XCTAssertEqual(error.statusCode, 422)
            XCTAssertEqual(error.errorDescription, "출발 좌표가 대한민국 지원 지역 밖입니다. 지도에서 국내 출발지를 선택해 주세요.")
        }
    }

    func testProviderFailureExposesSafeMessageWithoutFallback() async throws {
        let client = KakaoLiveRecommendationAPIClient(baseURL: URL(string: "http://provider.test")!, session: stubbedSession())
        let origin = OriginLocation(name: "출발지", coordinate: .init(latitude: 37.5665, longitude: 126.9780), source: .currentDevice)
        KakaoURLProtocolStub.register(host: "provider.test") { request in
            let data = Data("{\"detail\":\"Live recommendations are temporarily unavailable.\"}".utf8)
            return (HTTPURLResponse(url: request.url!, statusCode: 503, httpVersion: nil, headerFields: nil)!, data)
        }

        do {
            _ = try await client.recommend(from: origin, purpose: .cafe, maxTravelTime: .thirty)
            XCTFail("Expected backend error")
        } catch let error as KakaoLiveRecommendationAPIError {
            XCTAssertEqual(error.statusCode, 503)
            XCTAssertEqual(error.errorDescription, "Live recommendations are temporarily unavailable.")
        }
    }

    private func stubbedSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [KakaoURLProtocolStub.self]
        return URLSession(configuration: configuration)
    }
}

private final class KakaoURLProtocolStub: URLProtocol {
    static var requestHandlers: [String: (URLRequest) -> (HTTPURLResponse, Data)] = [:]
    static var lastRequest: URLRequest?
    static var lastBody: Data?

    static func register(host: String, handler: @escaping (URLRequest) -> (HTTPURLResponse, Data)) {
        requestHandlers[host] = handler
    }

    static func body(of request: URLRequest) -> Data? {
        if let body = request.httpBody { return body }
        guard let stream = request.httpBodyStream else { return nil }
        stream.open()
        defer { stream.close() }
        var data = Data()
        let bufferSize = 1_024
        var buffer = [UInt8](repeating: 0, count: bufferSize)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: bufferSize)
            guard count > 0 else { return nil }
            data.append(buffer, count: count)
        }
        return data
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let host = request.url?.host,
              let requestHandler = Self.requestHandlers[host] else {
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
