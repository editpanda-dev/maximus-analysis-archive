import SwiftUI

enum AppEntryPhase: Equatable {
    case splash
    case home
    case recommendation
}

@MainActor
final class AppEntryViewModel: ObservableObject {
    @Published private(set) var phase: AppEntryPhase = .splash

    func completeSplash() {
        phase = .home
    }

    func startRecommendation() {
        phase = .recommendation
    }

    func returnHome() {
        phase = .home
    }
}

struct AppEntryView: View {
    @StateObject private var viewModel = AppEntryViewModel()

    var body: some View {
        Group {
            switch viewModel.phase {
            case .splash:
                LaunchView(viewModel: viewModel)
            case .home:
                HomeView(onStartRecommendation: viewModel.startRecommendation)
            case .recommendation:
                ContentView()
            }
        }
    }
}

struct LaunchView: View {
    @ObservedObject var viewModel: AppEntryViewModel

    var body: some View {
        Text("어디가지")
            .font(.largeTitle.weight(.bold))
            .task {
                try? await Task.sleep(for: .seconds(1))
                viewModel.completeSplash()
            }
    }
}

struct HomeView: View {
    let onStartRecommendation: () -> Void

    var body: some View {
        VStack(spacing: 24) {
            Text("나에게 맞는 동네를 추천받아 보세요.")
                .foregroundStyle(.secondary)

            Button("추천 시작하기", action: onStartRecommendation)
                .buttonStyle(.borderedProminent)
                .accessibilityLabel("추천 조건 설정 열기")
        }
        .padding(24)
    }
}
