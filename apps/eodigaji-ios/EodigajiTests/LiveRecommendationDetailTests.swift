import CoreLocation
import MapKit
import XCTest
@testable import Eodigaji

final class LiveRecommendationDetailTests: XCTestCase {
    func testAppleMapsLocationLinkUsesSourceAndDestinationCoordinates() {
        let origin = OriginLocation(
            name: "출발 핀",
            coordinate: CLLocationCoordinate2D(latitude: 37.3389, longitude: 127.2697),
            source: .mapPin
        )
        let recommendation = LiveRecommendation(
            placeName: "서울숲",
            address: "서울 성동구 뚝섬로 273",
            destinationCoordinate: CLLocationCoordinate2D(latitude: 37.5444, longitude: 127.0374),
            expectedTravelTime: 2_280,
            distanceMeters: 12_300,
            routeSteps: []
        )

        let route = AppleMapsLocationLink(origin: origin, recommendation: recommendation)

        XCTAssertEqual(route.mapItems.count, 2)
        XCTAssertEqual(route.mapItems[0].placemark.coordinate.latitude, 37.3389, accuracy: 0.000_001)
        XCTAssertEqual(route.mapItems[0].placemark.coordinate.longitude, 127.2697, accuracy: 0.000_001)
        XCTAssertEqual(route.mapItems[1].placemark.coordinate.latitude, 37.5444, accuracy: 0.000_001)
        XCTAssertEqual(route.mapItems[1].placemark.coordinate.longitude, 127.0374, accuracy: 0.000_001)
        XCTAssertEqual(
            route.launchOptions[MKLaunchOptionsDirectionsModeKey] as? String,
            MKLaunchOptionsDirectionsModeTransit
        )
    }
}
