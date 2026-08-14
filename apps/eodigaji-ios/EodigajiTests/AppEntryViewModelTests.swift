import XCTest
@testable import Eodigaji

@MainActor
final class AppEntryViewModelTests: XCTestCase {
    func testSplashCompletesIntoHome() {
        let viewModel = AppEntryViewModel()

        XCTAssertEqual(viewModel.phase, .splash)
        viewModel.completeSplash()
        XCTAssertEqual(viewModel.phase, .home)
    }

    func testStartAndReturnUseFreshRecommendationEntry() {
        let viewModel = AppEntryViewModel()

        viewModel.completeSplash()
        viewModel.startRecommendation()
        XCTAssertEqual(viewModel.phase, .recommendation)

        viewModel.returnHome()
        XCTAssertEqual(viewModel.phase, .home)
    }
}
