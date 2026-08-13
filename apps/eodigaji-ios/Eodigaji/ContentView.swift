import Foundation
import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel: RecommendationViewModel
    @State private var isOriginSearchPresented = false
    @State private var isOriginPickerPresented = false

    @MainActor
    init(
        apiClient _: any RecommendationServicing = RecommendationAPIClient(),
        liveService: (any LiveRecommendationServicing)? = nil,
        locationService: (any LocationServicing)? = nil,
        originSearchService: (any OriginSearching)? = nil
    ) {
        _viewModel = StateObject(
            wrappedValue: RecommendationViewModel(
                liveService: liveService ?? KakaoLiveRecommendationAPIClient(),
                locationService: locationService,
                originSearchService: originSearchService
            )
        )
    }

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.shouldShowResults, let origin = viewModel.liveResultsOrigin {
                    liveResults(from: origin)
                } else {
                    conditionForm
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom, spacing: 0) {
                privacyNotice
            }
        }
        .sheet(isPresented: $isOriginSearchPresented) {
            OriginSearchSheet(viewModel: viewModel)
        }
        .sheet(isPresented: $isOriginPickerPresented) {
            NavigationStack {
                OriginPickerView(initialOrigin: viewModel.selectedOrigin) { origin in
                    viewModel.selectOrigin(origin)
                    isOriginPickerPresented = false
                }
                .navigationTitle("지도에서 출발지 선택")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button("닫기") {
                            isOriginPickerPresented = false
                        }
                    }
                }
            }
        }
        .task {
            await viewModel.requestInitialCurrentLocation()
        }
    }

    private var conditionForm: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("출발지 주변의 장소와 대중교통 경로를 카카오 기반 실시간 추천으로 확인합니다.")
                    .font(.body)
                    .foregroundStyle(.secondary)

                originSection
                recommendationConditions
                recommendButton
                requestState
            }
            .padding(20)
        }
        .navigationTitle("어디가지")
    }

    private var originSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("출발지")
                .font(.title3.weight(.semibold))

            if let origin = viewModel.selectedOrigin {
                VStack(alignment: .leading, spacing: 5) {
                    Label(origin.name, systemImage: origin.source.systemImageName)
                        .font(.headline)
                    Text(origin.source.koreanLabel)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("위도 \(origin.coordinate.latitude.formatted(.number.precision(.fractionLength(5)))), 경도 \(origin.coordinate.longitude.formatted(.number.precision(.fractionLength(5))))")
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color.accentColor.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                Text("현재 위치, 장소 검색 또는 지도 핀으로 출발지를 선택해 주세요.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 4)
            }

            HStack(spacing: 8) {
                Button {
                    Task { await viewModel.requestCurrentLocation() }
                } label: {
                    Label(
                        viewModel.isResolvingOrigin ? "확인 중" : "현재 위치",
                        systemImage: "location.fill"
                    )
                }
                .disabled(viewModel.isResolvingOrigin)

                Button {
                    isOriginSearchPresented = true
                } label: {
                    Label("장소 검색", systemImage: "magnifyingglass")
                }

                Button {
                    isOriginPickerPresented = true
                } label: {
                    Label("지도 핀", systemImage: "mappin.and.ellipse")
                }
            }
            .buttonStyle(.bordered)
            .labelStyle(.iconOnly)

            if let message = viewModel.originErrorMessage {
                Label(message, systemImage: "location.slash")
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
        }
    }

    private var recommendationConditions: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("추천 조건")
                .font(.title3.weight(.semibold))

            LabeledContent("이동 수단") {
                Text("대중교통")
                    .fontWeight(.semibold)
            }

            Picker("최대 이동 시간", selection: $viewModel.maxTravelTimeMinutes) {
                ForEach(MaxTravelTimeMinutes.allCases, id: \.rawValue) { minutes in
                    Text("\(minutes.rawValue)분").tag(minutes)
                }
            }
            .pickerStyle(.segmented)

            VStack(alignment: .leading, spacing: 10) {
                Text("추천 목적")
                    .font(.subheadline.weight(.semibold))

                LazyVGrid(
                    columns: [GridItem(.flexible()), GridItem(.flexible())],
                    spacing: 10
                ) {
                    ForEach(Purpose.allCases, id: \.rawValue) { purpose in
                        purposeButton(purpose)
                    }
                }
            }
        }
    }

    private func purposeButton(_ purpose: Purpose) -> some View {
        let isSelected = viewModel.purpose == purpose

        return Button {
            viewModel.purpose = purpose
        } label: {
            Text(purpose.koreanLabel)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
        }
        .buttonStyle(.bordered)
        .tint(isSelected ? .accentColor : .secondary)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isSelected ? Color.accentColor.opacity(0.12) : .clear)
        )
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    private var recommendButton: some View {
        Button {
            Task { await viewModel.recommendLive() }
        } label: {
            HStack(spacing: 8) {
                if viewModel.isLoading {
                    ProgressView().controlSize(.small)
                }
                Text(viewModel.isLoading ? "검색·경로 계산 중…" : "실시간 추천 받기")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .disabled(viewModel.isLoading || viewModel.selectedOrigin == nil)
    }

    @ViewBuilder
    private var requestState: some View {
        if viewModel.isLoading {
            HStack {
                Spacer()
                ProgressView("주변 장소를 찾고 대중교통 경로를 계산하는 중…")
                Spacer()
            }
            .padding(.vertical, 8)
        }

        if let message = viewModel.liveErrorMessage {
            VStack(alignment: .leading, spacing: 12) {
                Label("실시간 추천을 불러오지 못했어요", systemImage: "wifi.exclamationmark")
                    .font(.headline)
                Text(message)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Button("다시 시도") {
                    Task { await viewModel.retryLive() }
                }
                .buttonStyle(.bordered)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.red.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }

    private func liveResults(from origin: OriginLocation) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(origin.name)
                            .font(.headline)
                        Text("대중교통 · 최대 \((viewModel.liveResultsMaxTravelTime ?? viewModel.maxTravelTimeMinutes).rawValue)분")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text("\(viewModel.liveResults.count)곳")
                        .font(.subheadline.weight(.semibold))
                }

                if let updatedAt = viewModel.lastUpdatedAt {
                    Label(
                        "Apple MapKit 기준 예상 경로 · \(updatedAt.formatted(date: .omitted, time: .shortened)) 조회",
                        systemImage: "clock"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }

                if viewModel.liveResults.isEmpty {
                    ContentUnavailableView(
                        "확인된 대중교통 경로가 없어요",
                        systemImage: "tram.fill",
                        description: Text("이동 시간을 늘리거나 다른 출발지를 선택해 주세요. 다른 교통수단이나 fixture 결과로 대체하지 않습니다.")
                    )
                    .padding(.vertical, 32)
                } else {
                    LazyVStack(spacing: 12) {
                        ForEach(Array(viewModel.liveResults.enumerated()), id: \.offset) { _, recommendation in
                            NavigationLink {
                                LiveRecommendationDetailView(
                                    origin: origin,
                                    recommendation: recommendation
                                )
                            } label: {
                                LiveRecommendationCard(recommendation: recommendation)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .padding(20)
        }
        .navigationTitle("실시간 추천")
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Button("조건으로") {
                    viewModel.dismissResults()
                }
            }
        }
    }

    private var privacyNotice: some View {
        Text("출발 좌표는 이 앱의 백엔드로 전송하지 않으며, 장소 검색과 경로 계산을 위해 Apple 지도 서비스에서 사용됩니다.")
            .font(.caption2.weight(.semibold))
            .multilineTextAlignment(.center)
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(.thinMaterial)
    }
}

private struct OriginSearchSheet: View {
    @ObservedObject var viewModel: RecommendationViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        TextField("예: 모현 한국외대", text: $viewModel.originQuery)
                            .textInputAutocapitalization(.never)
                            .submitLabel(.search)
                            .onSubmit(search)
                        Button(action: search) {
                            Image(systemName: "magnifyingglass")
                        }
                        .disabled(
                            viewModel.isSearchingOrigins
                                || viewModel.originQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        )
                    }
                } footer: {
                    Text("선택한 출발지 근처를 우선해 Apple 지도에서 검색합니다.")
                }

                if viewModel.isSearchingOrigins {
                    HStack {
                        Spacer()
                        ProgressView("장소 검색 중…")
                        Spacer()
                    }
                } else if let message = viewModel.originSearchErrorMessage {
                    Label(message, systemImage: "exclamationmark.magnifyingglass")
                        .foregroundStyle(.red)
                } else if viewModel.hasCompletedOriginSearch && viewModel.originSearchResults.isEmpty {
                    ContentUnavailableView(
                        "검색 결과가 없어요",
                        systemImage: "magnifyingglass",
                        description: Text("검색어를 바꾸거나 지도에서 출발지 핀을 선택해 주세요.")
                    )
                } else if !viewModel.originSearchResults.isEmpty {
                    Section("검색 결과") {
                        ForEach(Array(viewModel.originSearchResults.enumerated()), id: \.offset) { _, origin in
                            Button {
                                viewModel.selectOrigin(origin)
                                dismiss()
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(origin.name)
                                        .foregroundStyle(.primary)
                                    Text("위도 \(origin.coordinate.latitude.formatted(.number.precision(.fractionLength(5)))), 경도 \(origin.coordinate.longitude.formatted(.number.precision(.fractionLength(5))))")
                                        .font(.caption.monospacedDigit())
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("출발지 검색")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("닫기") { dismiss() }
                }
            }
        }
    }

    private func search() {
        Task { await viewModel.searchOrigins() }
    }
}

private struct LiveRecommendationCard: View {
    let recommendation: LiveRecommendation

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(recommendation.placeName)
                    .font(.headline)
                Spacer()
                Text("\(recommendation.journeyTimeMinutes)분")
                    .font(.headline)
            }

            if !recommendation.address.isEmpty {
                Text(recommendation.address)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 6) {
                Label(distanceText(recommendation.distanceMeters), systemImage: "point.topleft.down.to.point.bottomright.curvepath")
                Spacer()
                Image(systemName: "chevron.right")
            }
            .font(.caption)
            .foregroundStyle(.secondary)

            if !recommendation.routeSteps.isEmpty {
                Text(recommendation.routeSteps.map(\.transportType.shortLabel).joined(separator: " → "))
                    .font(.caption.weight(.semibold))
                    .lineLimit(2)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .combine)
    }
}

func distanceText(_ meters: Double) -> String {
    if meters < 1_000 {
        return "\(Int(meters.rounded()))m"
    }

    return String(format: "%.1fkm", meters / 1_000)
}

extension Purpose {
    var koreanLabel: String {
        switch self {
        case .food: return "맛집"
        case .cafe: return "카페"
        case .date: return "데이트"
        case .shopping: return "쇼핑"
        case .culture: return "문화"
        case .rest: return "휴식"
        }
    }
}

extension LiveRouteTransportType {
    var shortLabel: String {
        switch self {
        case .walking: return "도보"
        case .transit: return "대중교통"
        case .automobile: return "자동차"
        case .other: return "이동"
        }
    }
}

private extension OriginLocation.Source {
    var koreanLabel: String {
        switch self {
        case .currentDevice: return "기기의 현재 위치"
        case .searchedPlace: return "Apple 지도 검색 결과"
        case .mapPin: return "지도에서 선택한 핀"
        }
    }

    var systemImageName: String {
        switch self {
        case .currentDevice: return "location.fill"
        case .searchedPlace: return "magnifyingglass"
        case .mapPin: return "mappin"
        }
    }
}
