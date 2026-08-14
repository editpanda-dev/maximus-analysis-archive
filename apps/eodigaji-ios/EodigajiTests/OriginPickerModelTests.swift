import CoreLocation
import XCTest
@testable import Eodigaji

@MainActor
final class OriginPickerModelTests: XCTestCase {
    func testPinIsOnlyCommittedWhenUserConfirmsIt() {
        var committedOrigins: [OriginLocation] = []
        let model = OriginPickerModel(initialOrigin: nil) { committedOrigins.append($0) }
        let pin = CLLocationCoordinate2D(latitude: 37.5895, longitude: 127.0577)

        model.selectPin(at: pin)

        XCTAssertEqual(model.selectedOrigin.coordinate.latitude, 37.5895, accuracy: 0.000_001)
        XCTAssertTrue(committedOrigins.isEmpty)

        model.confirmSelection()

        XCTAssertEqual(committedOrigins.count, 1)
        XCTAssertEqual(committedOrigins[0].coordinate.longitude, 127.0577, accuracy: 0.000_001)
    }
}
