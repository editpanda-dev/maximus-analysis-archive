import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel: RecommendationViewModel

    init(apiClient: any RecommendationServicing = RecommendationAPIClient()) {
        _viewModel = StateObject(
            wrappedValue: RecommendationViewModel(service: apiClient)
        )
    }

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.shouldShowResults, let response = viewModel.response {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            recommendationResults(response)
                        }
                        .padding(20)
                    }
                    .navigationTitle("추천 결과")
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) {
                            Button("조건으로") {
                                viewModel.dismissResults()
                            }
                        }
                    }
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 24) {
                            Text("출발지와 조건을 입력하면 목적에 맞는 장소를 찾아드려요.")
                                .font(.body)
                                .foregroundStyle(.secondary)
                            recommendationForm
                            recommendButton
                            requestState
                        }
                        .padding(20)
                    }
                    .navigationTitle("어디가지")
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .top, spacing: 0) {
                fixtureDisclaimer
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                fixtureDisclaimer
            }
        }
    }

    private var recommendationForm: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("추천 조건")
                .font(.title3.weight(.semibold))

            VStack(alignment: .leading, spacing: 8) {
                Text("출발지")
                    .font(.subheadline.weight(.semibold))
                TextField("예: 회기역", text: $viewModel.origin)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .accessibilityLabel("출발지")
            }

            LabeledContent("이동 수단") {
                Text(viewModel.transportMode.koreanLabel)
                    .fontWeight(.semibold)
                    .accessibilityLabel("이동 수단 대중교통, 고정")
            }

            Picker("최대 이동 시간", selection: $viewModel.maxTravelTimeMinutes) {
                ForEach(MaxTravelTimeMinutes.allCases, id: \.rawValue) { minutes in
                    Text("\(minutes.rawValue)분")
                        .tag(minutes)
                }
            }
            .pickerStyle(.segmented)
            .accessibilityLabel("최대 이동 시간")

            Picker("시간대", selection: $viewModel.timeSlot) {
                ForEach(TimeSlot.allCases, id: \.rawValue) { timeSlot in
                    Text(timeSlot.koreanLabel)
                        .tag(timeSlot)
                }
            }
            .pickerStyle(.menu)
            .accessibilityLabel("시간대")

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
        let isSelected = viewModel.purpose.rawValue == purpose.rawValue

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
        .accessibilityLabel("추천 목적 \(purpose.koreanLabel)")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    private var recommendButton: some View {
        Button {
            Task {
                await viewModel.recommend()
            }
        } label: {
            HStack(spacing: 8) {
                if viewModel.isLoading {
                    ProgressView()
                        .controlSize(.small)
                }
                Text(viewModel.isLoading ? "추천 받는 중…" : "추천 받기")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .controlSize(.large)
        .disabled(
            viewModel.isLoading
                || viewModel.origin.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        )
        .accessibilityLabel("추천 받기")
        .accessibilityValue(viewModel.isLoading ? "불러오는 중" : "준비됨")
    }

    @ViewBuilder
    private var requestState: some View {
        if viewModel.isLoading {
            HStack {
                Spacer()
                ProgressView("추천을 불러오는 중…")
                Spacer()
            }
            .padding(.vertical, 8)
        }

        if let errorMessage = viewModel.errorMessage {
            VStack(alignment: .leading, spacing: 12) {
                Label("추천을 불러오지 못했어요", systemImage: "wifi.exclamationmark")
                    .font(.headline)
                Text(errorMessage)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Button("다시 시도") {
                    Task {
                        await viewModel.retry()
                    }
                }
                .buttonStyle(.bordered)
                .accessibilityHint("같은 조건으로 추천을 다시 요청합니다")
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.red.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .accessibilityElement(children: .contain)
        }
    }

    private func recommendationResults(_ response: RecommendationResponse) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("추천 결과")
                    .font(.title3.weight(.semibold))
                Spacer()
                Text("후보 \(response.eligibleCount)곳")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            if response.recommendations.isEmpty {
                Text("조건에 맞는 추천 장소가 없습니다. 조건을 바꿔 다시 시도해 보세요.")
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            } else {
                LazyVStack(spacing: 12) {
                    ForEach(response.recommendations, id: \.id) { recommendation in
                        RecommendationResultCard(recommendation: recommendation)
                    }
                }
            }

            DisclosureGroup("추천 기준 및 한계") {
                VStack(alignment: .leading, spacing: 8) {
                    LabeledContent("랭킹 기준") {
                        Text(response.rankingBasis.rawValue)
                            .font(.caption)
                    }
                    LabeledContent("응답 유형") {
                        Text(response.fixture ? "fixture" : "fixture 아님")
                            .font(.caption)
                    }
                    Text(response.limitations)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding(.top, 8)
            }
            .font(.subheadline.weight(.semibold))
            .accessibilityHint("추천 순위의 기준과 데이터 한계를 보여줍니다")
        }
    }

    private var fixtureDisclaimer: some View {
        Text("Fixture 기반 데모입니다. 실시간 대중교통 정보가 아니며, 개인화 추천이나 결과의 인과관계를 보장하지 않습니다.")
            .font(.footnote.weight(.semibold))
            .multilineTextAlignment(.center)
            .foregroundStyle(.orange)
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(.thinMaterial)
            .accessibilityLabel("Fixture 기반 데모이며 실시간 대중교통 정보가 아니고 개인화 추천이나 결과의 인과관계를 보장하지 않음")
    }
}

private struct RecommendationResultCard: View {
    let recommendation: Recommendation

    private static let wonFormatter: NumberFormatter = {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.locale = Locale(identifier: "ko_KR")
        return formatter
    }()

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(recommendation.name)
                        .font(.headline)
                    Text(recommendation.district)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                Spacer(minLength: 8)

                Text("대중교통 \(recommendation.journeyTimeMinutes)분")
                    .font(.subheadline.weight(.semibold))
                    .multilineTextAlignment(.trailing)
            }

            if !recommendation.tags.isEmpty {
                HStack(spacing: 6) {
                    ForEach(recommendation.tags, id: \.self) { tag in
                        Text("#\(tag)")
                            .font(.caption)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.accentColor.opacity(0.1))
                            .clipShape(Capsule())
                    }
                }
            }

            HStack(alignment: .firstTextBaseline) {
                Text(costText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Spacer()
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("추천 이유")
                    .font(.caption.weight(.semibold))
                Text(recommendation.reason)
                    .font(.subheadline)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(
            "\(recommendation.name), \(recommendation.district), 대중교통 \(recommendation.journeyTimeMinutes)분, \(costText), 추천 이유 \(recommendation.reason)"
        )
    }

    private var costText: String {
        guard case .available = recommendation.costStatus,
              let costWon = recommendation.costWon else {
            return "요금 정보 없음"
        }

        let formatted = Self.wonFormatter.string(from: NSNumber(value: costWon)) ?? "\(costWon)"
        return "\(formatted)원"
    }
}

private extension TransportMode {
    var koreanLabel: String {
        switch self {
        case .publicTransit:
            return "대중교통"
        }
    }
}

private extension TimeSlot {
    var koreanLabel: String {
        switch self {
        case .morning:
            return "아침"
        case .lunch:
            return "점심"
        case .afternoon:
            return "오후"
        case .evening:
            return "저녁"
        case .night:
            return "밤"
        }
    }
}

private extension Purpose {
    var koreanLabel: String {
        switch self {
        case .food:
            return "맛집"
        case .cafe:
            return "카페"
        case .date:
            return "데이트"
        case .shopping:
            return "쇼핑"
        case .culture:
            return "문화"
        case .rest:
            return "휴식"
        }
    }
}
