import CoreLocation
import MapKit
import SwiftUI

struct OriginPickerView: View {
    @StateObject private var model: OriginPickerModel
    @State private var cameraPosition: MapCameraPosition

    init(
        initialOrigin: OriginLocation? = nil,
        onSelect: @escaping (OriginLocation) -> Void
    ) {
        let origin = initialOrigin ?? OriginPickerModel.defaultOrigin

        _model = StateObject(wrappedValue: OriginPickerModel(initialOrigin: origin, onSelect: onSelect))
        _cameraPosition = State(
            initialValue: .region(OriginPickerModel.cameraRegion(for: origin))
        )
    }

    var body: some View {
        MapReader { proxy in
            Map(position: $cameraPosition) {
                Marker(model.selectedOrigin.name, coordinate: model.selectedOrigin.coordinate)
            }
            .onTapGesture { position in
                guard let coordinate = proxy.convert(position, from: .local) else {
                    return
                }

                model.selectPin(at: coordinate)
            }
        }
        .onAppear {
            cameraPosition = .region(model.initialCameraRegion)
        }
        .accessibilityLabel("지도에서 출발지 핀 선택")
    }
}

@MainActor
final class OriginPickerModel: ObservableObject {
    static let defaultOrigin = OriginLocation(
        name: "선택한 위치",
        coordinate: CLLocationCoordinate2D(latitude: 37.5665, longitude: 126.9780),
        source: .mapPin
    )

    @Published private(set) var selectedOrigin: OriginLocation
    private let onSelect: (OriginLocation) -> Void

    init(initialOrigin: OriginLocation?, onSelect: @escaping (OriginLocation) -> Void) {
        selectedOrigin = initialOrigin ?? Self.defaultOrigin
        self.onSelect = onSelect
    }

    var initialCameraRegion: MKCoordinateRegion {
        Self.cameraRegion(for: selectedOrigin)
    }

    static func cameraRegion(for origin: OriginLocation) -> MKCoordinateRegion {
        MKCoordinateRegion(
            center: origin.coordinate,
            span: MKCoordinateSpan(latitudeDelta: 0.02, longitudeDelta: 0.02)
        )
    }

    func selectPin(at coordinate: CLLocationCoordinate2D) {
        let origin = OriginLocation(
            name: "선택한 위치",
            coordinate: coordinate,
            source: .mapPin
        )
        selectedOrigin = origin
        onSelect(origin)
    }
}
