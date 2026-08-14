# 홈·스플래시 진입 흐름 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 앱 실행 시 스플래시와 홈을 거쳐 사용자가 기존 추천 조건 화면으로 진입하게 한다.

**Architecture:** `AppEntryViewModel`이 `splash → home → recommendation` 진입 상태를 소유한다. `LaunchView`, `HomeView`, `AppEntryView`는 화면 전환만 책임지고, 기존 `ContentView`는 추천 조건·동네·점포 흐름을 그대로 유지하되 홈으로 돌아갈 콜백만 받는다.

**Tech Stack:** SwiftUI, XCTest, iOS Simulator

## Global Constraints

- 스플래시는 1초 후 자동으로 홈으로 전환하며 네트워크·위치·추천 API를 호출하지 않는다.
- 홈은 `추천 시작하기` 단일 CTA만 제공한다.
- 홈 CTA는 새 `ContentView`를 열며, 조건 설정에서 뒤로가기는 홈으로 돌아간다.
- 홈으로 돌아온 뒤 이전 추천 결과·입력 조건을 보존하지 않는다.
- 기존 카카오 추천·행정동 API 계약과 키 처리 방식을 변경하지 않는다.
- CTA와 뒤로가기에는 접근성 레이블을 제공한다.

---

### Task 1: 앱 진입 상태와 스플래시·홈 화면

**Files:**
- Create: `apps/eodigaji-ios/Eodigaji/AppEntryView.swift`
- Create: `apps/eodigaji-ios/EodigajiTests/AppEntryViewModelTests.swift`
- Modify: `apps/eodigaji-ios/Eodigaji/EodigajiApp.swift`
- Modify: `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`

**Interfaces:**
- Produces `AppEntryPhase` (`splash`, `home`, `recommendation`).
- Produces `@MainActor AppEntryViewModel` with `completeSplash()`, `startRecommendation()`, and `returnHome()`.
- `EodigajiApp` roots `AppEntryView` instead of `ContentView`.

- [ ] **Step 1: Write failing state tests.**

```swift
@MainActor
func testSplashCompletesIntoHome() {
    let viewModel = AppEntryViewModel()
    XCTAssertEqual(viewModel.phase, .splash)
    viewModel.completeSplash()
    XCTAssertEqual(viewModel.phase, .home)
}

@MainActor
func testStartAndReturnUseFreshRecommendationEntry() {
    let viewModel = AppEntryViewModel()
    viewModel.completeSplash()
    viewModel.startRecommendation()
    XCTAssertEqual(viewModel.phase, .recommendation)
    viewModel.returnHome()
    XCTAssertEqual(viewModel.phase, .home)
}
```

- [ ] **Step 2: Run focused XCTest and confirm missing symbols fail.**

Run: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' -only-testing:EodigajiTests/AppEntryViewModelTests`

- [ ] **Step 3: Implement the state model and stateless entry views.**

```swift
@MainActor
final class AppEntryViewModel: ObservableObject {
    @Published private(set) var phase: AppEntryPhase = .splash
    func completeSplash() { phase = .home }
    func startRecommendation() { phase = .recommendation }
    func returnHome() { phase = .home }
}
```

`LaunchView` shows the existing app name and uses `.task { try? await Task.sleep(for: .seconds(1)); viewModel.completeSplash() }`. `HomeView` displays one explanatory line and a `추천 시작하기` button with accessibility label `추천 조건 설정 열기`. `AppEntryView` switches on phase and constructs `ContentView(onReturnHome: viewModel.returnHome)` only for `.recommendation`.

- [ ] **Step 4: Register files and make the entry view the app root.**

```swift
WindowGroup {
    AppEntryView()
}
```

Add the source and test files to the application/test target sections of `project.pbxproj`.

- [ ] **Step 5: Run focused/full XCTest, simulator build, and diff check.**

Run: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' && xcodebuild build -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' && git diff --check`

- [ ] **Step 6: Commit the entry flow.**

```bash
git add apps/eodigaji-ios/Eodigaji/AppEntryView.swift apps/eodigaji-ios/Eodigaji/EodigajiApp.swift apps/eodigaji-ios/EodigajiTests/AppEntryViewModelTests.swift apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj
git commit -m "feat: add home and splash entry flow"
```

### Task 2: 추천 조건 화면의 홈 복귀와 시뮬레이터 검증

**Files:**
- Modify: `apps/eodigaji-ios/Eodigaji/ContentView.swift`
- Modify: `apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift`

**Interfaces:**
- Consumes `ContentView(onReturnHome: @escaping () -> Void)`.
- Produces an inline condition-screen back action that invokes `onReturnHome`.

- [ ] **Step 1: Write a failing construction/state-reset regression test.**

```swift
@MainActor
func testFreshContentViewModelStartsWithoutDistrictResults() {
    let viewModel = RecommendationViewModel(districtService: DistrictStub())
    XCTAssertFalse(viewModel.shouldShowResults)
    XCTAssertTrue(viewModel.liveDistricts.isEmpty)
    XCTAssertNil(viewModel.selectedDistrict)
}
```

- [ ] **Step 2: Run the focused XCTest.**

Run: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' -only-testing:EodigajiTests/RecommendationViewModelTests`

- [ ] **Step 3: Add the condition-screen home back action without changing result-detail back behavior.**

```swift
init(
    onReturnHome: @escaping () -> Void = {},
    districtService: (any DistrictRecommendationServicing)? = nil,
    ...
) {
    self.onReturnHome = onReturnHome
    // existing view model construction
}
```

Add a leading toolbar button only while the condition form is visible. It calls `onReturnHome`, has accessibility label `홈으로 돌아가기`, and does not replace the existing district-detail back button.

- [ ] **Step 4: Verify full iOS behavior.**

Run full XCTest and simulator build. Install and launch the app on the iPhone 17 Pro simulator; confirm splash → home → `추천 시작하기` → conditions → 홈 복귀 order. No API request is expected before pressing the existing real-time recommendation button.

- [ ] **Step 5: Commit the return action.**

```bash
git add apps/eodigaji-ios/Eodigaji/ContentView.swift apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift
git commit -m "feat: return from recommendation setup to home"
```

## Self-review

- Spec coverage: Task 1 implements splash timing, home CTA, root state, accessibility, and no backend calls; Task 2 implements the required home return and fresh recommendation-session behavior.
- No-placeholder scan: complete.
- Type consistency: `AppEntryView` constructs `ContentView(onReturnHome:)`; `ContentView` invokes the closure only from its condition form; `AppEntryViewModel.returnHome()` resets the phase to `.home`.
