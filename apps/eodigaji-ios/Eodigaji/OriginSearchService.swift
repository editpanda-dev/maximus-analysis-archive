import CoreLocation
import MapKit

@MainActor
public protocol OriginSearching: AnyObject {
    func search(query: String, region: MKCoordinateRegion?) async throws -> [OriginLocation]
}

@MainActor
public final class OriginSearchService: OriginSearching {
    private let localSearch: (String, MKCoordinateRegion?) async throws -> [MKMapItem]

    public init() {
        localSearch = { query, region in
            let request = MKLocalSearch.Request()
            request.naturalLanguageQuery = query
            if let region {
                request.region = region
            }

            return try await MKLocalSearch(request: request).start().mapItems
        }
    }

    init(localSearch: @escaping (String, MKCoordinateRegion?) async throws -> [MKMapItem]) {
        self.localSearch = localSearch
    }

    public func search(query: String, region: MKCoordinateRegion? = nil) async throws -> [OriginLocation] {
        let trimmedQuery = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedQuery.isEmpty else {
            return []
        }

        return try await localSearch(trimmedQuery, region).map { mapItem in
            OriginLocation(
                name: displayName(for: mapItem, fallback: trimmedQuery),
                coordinate: mapItem.placemark.coordinate,
                source: .searchedPlace
            )
        }
    }

    private func displayName(for mapItem: MKMapItem, fallback: String) -> String {
        let name = mapItem.name?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return name.isEmpty ? fallback : name
    }
}
