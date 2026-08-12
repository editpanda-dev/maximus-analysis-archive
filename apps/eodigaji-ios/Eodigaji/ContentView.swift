import SwiftUI

struct ContentView: View {
    private let apiClient: any RecommendationAPIClientProtocol

    init(apiClient: any RecommendationAPIClientProtocol = RecommendationAPIClient()) {
        self.apiClient = apiClient
    }

    var body: some View {
        VStack(spacing: 20) {
            Text("어디가지")
                .font(.largeTitle.weight(.bold))

            Text("출발지와 조건을 입력하면 목적에 맞는 장소를 찾아드려요.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            Text("데모 fixture / 실시간 대중교통 정보 아님")
                .font(.footnote.weight(.semibold))
                .multilineTextAlignment(.center)
                .foregroundStyle(.orange)
                .padding(.horizontal)
                .accessibilityLabel("데모 fixture이며 실시간 대중교통 정보가 아님")
        }
        .padding(24)
    }
}
