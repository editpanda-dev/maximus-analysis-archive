import Foundation
import XCTest
@testable import Eodigaji

@MainActor
final class KakaoDistrictRecommendationAPIClientTests: XCTestCase {
    private let origin = OriginLocation(
        name: "모현 한국외대",
        coordinate: .init(latitude: 37.3389, longitude: 127.2697),
        source: .searchedPlace
    )

    func testPostsSnakeCaseRequestToDistrictEndpoint() async throws {
        let responseData = districtResponse(districts: [])
        DistrictURLProtocolStub.register(host: "district-request.test") { request in
            DistrictURLProtocolStub.lastRequest = request
            DistrictURLProtocolStub.lastBody = DistrictURLProtocolStub.body(of: request)
            return (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, responseData)
        }
        let client = KakaoDistrictRecommendationAPIClient(
            baseURL: URL(string: "http://district-request.test")!,
            session: stubbedSession()
        )

        _ = try await client.recommendDistricts(from: origin, purpose: .cafe, maxTravelTime: .thirty)

        XCTAssertEqual(DistrictURLProtocolStub.lastRequest?.httpMethod, "POST")
        XCTAssertEqual(DistrictURLProtocolStub.lastRequest?.url?.path, "/v1/live-district-recommendations")
        let body = try XCTUnwrap(DistrictURLProtocolStub.lastBody)
        let json = try XCTUnwrap(try JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["origin_name"] as? String, "모현 한국외대")
        XCTAssertEqual(try XCTUnwrap(json["origin_latitude"] as? Double), 37.3389, accuracy: 0.000001)
        XCTAssertEqual(try XCTUnwrap(json["origin_longitude"] as? Double), 127.2697, accuracy: 0.000001)
        XCTAssertEqual(json["purpose"] as? String, "cafe")
        XCTAssertEqual(json["max_travel_time_minutes"] as? Int, 30)
        XCTAssertNil(json["originLatitude"])
        XCTAssertNil(json["maxTravelTimeMinutes"])
    }

    func testMapsDistrictResponseAndRetainsOnlyItsPlaces() async throws {
        let responseData = districtResponse(
            districts: [
                district(name: "모현읍", fastestTravelTime: 1200, places: ["썸카페", "이디야"])
            ]
        )
        DistrictURLProtocolStub.register(host: "district-mapping.test") { request in
            (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, responseData)
        }
        let client = KakaoDistrictRecommendationAPIClient(
            baseURL: URL(string: "http://district-mapping.test")!,
            session: stubbedSession()
        )

        let districts = try await client.recommendDistricts(from: origin, purpose: .cafe, maxTravelTime: .thirty)

        XCTAssertEqual(districts.map(\.districtName), ["모현읍"])
        XCTAssertEqual(districts[0].fastestTravelTime, 1200)
        XCTAssertEqual(districts[0].placeCount, 2)
        XCTAssertEqual(districts[0].places.map(\.placeName), ["썸카페", "이디야"])
    }

    func testReturnsNoDistrictsForNoEligibleCandidates() async throws {
        let responseData = districtResponse(districts: [], resultStatus: "no_eligible_candidates", eligibleCount: 0)
        DistrictURLProtocolStub.register(host: "district-empty.test") { request in
            (HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, responseData)
        }
        let client = KakaoDistrictRecommendationAPIClient(
            baseURL: URL(string: "http://district-empty.test")!,
            session: stubbedSession()
        )

        let districts = try await client.recommendDistricts(from: origin, purpose: .cafe, maxTravelTime: .thirty)

        XCTAssertEqual(districts, [])
    }

    func testPropagatesBackendHTTPErrorWithServerMessage() async throws {
        DistrictURLProtocolStub.register(host: "district-error.test") { request in
            let data = Data("{\"detail\":\"Live recommendations are temporarily unavailable.\"}".utf8)
            return (HTTPURLResponse(url: request.url!, statusCode: 503, httpVersion: nil, headerFields: nil)!, data)
        }
        let client = KakaoDistrictRecommendationAPIClient(
            baseURL: URL(string: "http://district-error.test")!,
            session: stubbedSession()
        )

        do {
            _ = try await client.recommendDistricts(from: origin, purpose: .cafe, maxTravelTime: .thirty)
            XCTFail("Expected backend error")
        } catch let error as KakaoLiveRecommendationAPIError {
            XCTAssertEqual(error.statusCode, 503)
            XCTAssertEqual(error.errorDescription, "Live recommendations are temporarily unavailable.")
        }
    }

    private func stubbedSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [DistrictURLProtocolStub.self]
        return URLSession(configuration: configuration)
    }

    private func districtResponse(
        districts: [[String: Any]],
        resultStatus: String = "ok",
        eligibleCount: Int? = nil
    ) -> Data {
        try! JSONSerialization.data(withJSONObject: [
            "result_status": resultStatus,
            "provider": "kakao",
            "queried_at": "2026-08-13T12:00:00Z",
            "eligible_count": eligibleCount ?? districts.reduce(0) { $0 + ($1["place_count"] as! Int) },
            "districts": districts,
            "fixture": false,
            "limitations": "Provider-supplied routes only."
        ])
    }

    private func district(name: String, fastestTravelTime: Int, places: [String]) -> [String: Any] {
        [
            "district_name": name,
            "fastest_travel_time_seconds": fastestTravelTime,
            "place_count": places.count,
            "places": places.enumerated().map { index, placeName in
                [
                    "place_name": placeName,
                    "address": "경기 용인시 처인구 모현읍 외대로 \(42 + index)",
                    "destination_latitude": 37.3345 + Double(index) * 0.001,
                    "destination_longitude": 127.2675 + Double(index) * 0.001,
                    "expected_travel_time_seconds": fastestTravelTime + index * 60,
                    "distance_meters": 1000 + index * 100,
                    "route_steps": [[
                        "instruction": "정류장까지 도보",
                        "distance_meters": 200,
                        "duration_seconds": 180,
                        "transport_mode": "walking"
                    ]]
                ]
            }
        ]
    }
}

private final class DistrictURLProtocolStub: URLProtocol {
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
        var buffer = [UInt8](repeating: 0, count: 1_024)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
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
