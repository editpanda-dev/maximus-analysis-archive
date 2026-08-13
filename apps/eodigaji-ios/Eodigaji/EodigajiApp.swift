import SwiftUI

@main
struct EodigajiApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView(districtService: KakaoDistrictRecommendationAPIClient())
        }
    }
}
