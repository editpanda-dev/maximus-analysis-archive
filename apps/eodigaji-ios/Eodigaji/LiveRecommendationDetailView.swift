import MapKit
import SwiftUI

struct AppleMapsLocationLink {
    let mapItems: [MKMapItem]
    let launchOptions: [String: Any]

    init(origin: OriginLocation, recommendation: LiveRecommendation) {
        let sourceItem = MKMapItem(
            placemark: MKPlacemark(coordinate: origin.coordinate)
        )
        sourceItem.name = origin.name

        let destinationItem = MKMapItem(
            placemark: MKPlacemark(coordinate: recommendation.destinationCoordinate)
        )
        destinationItem.name = recommendation.placeName

        mapItems = [sourceItem, destinationItem]
        launchOptions = [
            MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeTransit
        ]
    }

    func open() {
        MKMapItem.openMaps(with: mapItems, launchOptions: launchOptions)
    }
}

struct LiveRecommendationDetailView: View {
    let origin: OriginLocation
    let recommendation: LiveRecommendation

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(recommendation.placeName)
                        .font(.title2.weight(.bold))

                    if !recommendation.address.isEmpty {
                        Text(recommendation.address)
                            .foregroundStyle(.secondary)
                    }

                    HStack(spacing: 16) {
                        Label(
                            "약 \(recommendation.journeyTimeMinutes)분",
                            systemImage: "clock.fill"
                        )
                        Label(
                            distanceText(recommendation.distanceMeters),
                            systemImage: "point.topleft.down.to.point.bottomright.curvepath"
                        )
                    }
                    .font(.subheadline.weight(.semibold))
                }

                RouteMapView(origin: origin, recommendation: recommendation)

                VStack(alignment: .leading, spacing: 8) {
                    Text("출발지")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                    Label(origin.name, systemImage: "location.fill")
                        .font(.headline)
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.accentColor.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 12))

                VStack(alignment: .leading, spacing: 12) {
                    Text("상세 경로")
                        .font(.title3.weight(.semibold))

                    Text("카카오 대중교통 경로의 도보·탑승 구간을 지도와 순서대로 보여드립니다.")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    if recommendation.routeSteps.isEmpty {
                        Text("카카오 대중교통 경로에서 단계별 안내를 제공하지 않았습니다.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .padding(.vertical, 8)
                    } else {
                        ForEach(Array(recommendation.routeSteps.enumerated()), id: \.offset) { offset, step in
                            LiveRouteStepCard(number: offset + 1, step: step)
                        }
                    }
                }

                Button {
                    AppleMapsLocationLink(origin: origin, recommendation: recommendation).open()
                } label: {
                    Label("Apple 지도에서 위치 열기", systemImage: "map.fill")
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)

                Text("표시된 시간·거리·이동 단계는 카카오 대중교통 경로가 제공한 예상값입니다. Apple 지도에서 위치를 열면 별도의 최신 경로가 계산될 수 있습니다. 요금, 혼잡도, 도착 시각 또는 환승 성공을 보장하지 않습니다.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(20)
        }
        .navigationTitle("경로 상세")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct LiveRouteStepCard: View {
    let number: Int
    let step: LiveRouteStep

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                Circle()
                    .fill(Color.accentColor.opacity(0.14))
                    .frame(width: 34, height: 34)
                Image(systemName: step.transportType.systemImageName)
                    .foregroundStyle(.tint)
            }

            VStack(alignment: .leading, spacing: 5) {
                HStack {
                    Text("\(number). \(step.transportType.shortLabel)")
                        .font(.subheadline.weight(.semibold))
                    Spacer()
                    Text(distanceText(step.distanceMeters))
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
                if step.duration > 0 {
                    Text("약 \(max(1, Int(ceil(step.duration / 60))))분 · \(distanceText(step.distanceMeters))")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
                Text(step.instructions)
                    .font(.subheadline)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
    }
}

private struct RouteMapView: View {
    let origin: OriginLocation
    let recommendation: LiveRecommendation

    private var mapRegion: MKCoordinateRegion {
        let points = [origin.coordinate, recommendation.destinationCoordinate]
            + recommendation.routeSteps.flatMap { $0.pathCoordinates.map(\.coordinate) }
        let latitudes = points.map(\.latitude)
        let longitudes = points.map(\.longitude)
        guard let minLatitude = latitudes.min(), let maxLatitude = latitudes.max(),
              let minLongitude = longitudes.min(), let maxLongitude = longitudes.max() else {
            return MKCoordinateRegion(center: origin.coordinate, span: .init(latitudeDelta: 0.02, longitudeDelta: 0.02))
        }
        return MKCoordinateRegion(
            center: .init(latitude: (minLatitude + maxLatitude) / 2, longitude: (minLongitude + maxLongitude) / 2),
            span: .init(latitudeDelta: max(0.01, (maxLatitude - minLatitude) * 1.35), longitudeDelta: max(0.01, (maxLongitude - minLongitude) * 1.35))
        )
    }

    var body: some View {
        Map(initialPosition: .region(mapRegion)) {
            Marker("출발", coordinate: origin.coordinate)
                .tint(.green)
            Marker(recommendation.placeName, coordinate: recommendation.destinationCoordinate)
                .tint(.red)
            ForEach(Array(recommendation.routeSteps.enumerated()), id: \.offset) { _, step in
                let coordinates = step.pathCoordinates.map(\.coordinate)
                if coordinates.count > 1 {
                    MapPolyline(coordinates: coordinates)
                        .stroke(step.transportType == .walking ? .orange : .blue, lineWidth: 5)
                }
            }
        }
        .mapStyle(.standard(elevation: .realistic))
        .frame(height: 240)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(alignment: .topLeading) {
            Text("주황: 도보 · 파랑: 대중교통")
                .font(.caption2.weight(.medium))
                .padding(8)
                .background(.ultraThinMaterial, in: Capsule())
                .padding(10)
        }
        .accessibilityLabel("카카오 대중교통 경로 지도")
    }
}

private extension LiveRouteTransportType {
    var systemImageName: String {
        switch self {
        case .walking: return "figure.walk"
        case .transit: return "tram.fill"
        case .automobile: return "car.fill"
        case .other: return "arrow.forward"
        }
    }
}
