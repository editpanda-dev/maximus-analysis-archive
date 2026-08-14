import CoreLocation
import MapKit
import XCTest
@testable import Eodigaji

@MainActor
final class OriginSearchServiceTests: XCTestCase {
    func testSearchMapsLocalSearchResultToNamedCoordinateOrigin() async throws {
        let coordinate = CLLocationCoordinate2D(latitude: 37.1683, longitude: 127.1790)
        let mapItem = MKMapItem(placemark: MKPlacemark(coordinate: coordinate))
        mapItem.name = "모현 한국외대"
        let service = OriginSearchService(localSearch: { _, _ in [mapItem] })

        let results = try await service.search(query: "모현 한국외대", region: nil)

        XCTAssertEqual(results, [
            OriginLocation(
                name: "모현 한국외대",
                coordinate: coordinate,
                source: .searchedPlace
            )
        ])
    }

    func testSelectingMapPinDeliversCoordinateToCallback() {
        let coordinate = CLLocationCoordinate2D(latitude: 37.1683, longitude: 127.1790)
        var callbackOrigin: OriginLocation?
        let picker = OriginPickerModel(initialOrigin: nil) { origin in
            callbackOrigin = origin
        }

        picker.selectPin(at: coordinate)

        XCTAssertEqual(callbackOrigin?.coordinate.latitude, 37.1683)
        XCTAssertEqual(callbackOrigin?.coordinate.longitude, 127.1790)
        XCTAssertEqual(callbackOrigin?.source, .mapPin)
    }

    func testMapPickerCameraStartsAtTheDisplayedOrigin() {
        let displayedOrigin = OriginLocation(
            name: "회기역",
            coordinate: CLLocationCoordinate2D(latitude: 37.5895, longitude: 127.0577),
            source: .searchedPlace
        )
        let picker = OriginPickerModel(initialOrigin: displayedOrigin) { _ in }

        let region = picker.initialCameraRegion

        XCTAssertEqual(region.center.latitude, 37.5895, accuracy: 0.00001)
        XCTAssertEqual(region.center.longitude, 127.0577, accuracy: 0.00001)
    }
}
