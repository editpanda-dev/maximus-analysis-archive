import CoreLocation

public struct OriginLocation: Equatable {
    public enum Source: Equatable {
        case currentDevice
    }

    public let name: String
    public let coordinate: CLLocationCoordinate2D
    public let source: Source

    public init(name: String, coordinate: CLLocationCoordinate2D, source: Source) {
        self.name = name
        self.coordinate = coordinate
        self.source = source
    }

    public static func == (lhs: OriginLocation, rhs: OriginLocation) -> Bool {
        lhs.name == rhs.name
            && lhs.coordinate.latitude == rhs.coordinate.latitude
            && lhs.coordinate.longitude == rhs.coordinate.longitude
            && lhs.source == rhs.source
    }
}
