# Live MapKit Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 위치·검색·지도 핀을 출발점으로 사용해 목적별 장소와 대중교통 경로를 실시간 추천한다.

**Architecture:** `LocationService`, `OriginSearchService`, `LiveRecommendationService`를 MapKit 의존성 경계로 분리한다. `RecommendationViewModel`은 출발 좌표와 실시간 결과를 소유하고 SwiftUI는 검색·핀·경로 상세를 표시한다.

**Tech Stack:** SwiftUI, MapKit, CoreLocation, XCTest, iOS 17+

## Global Constraints

- MapKit 외 외부 SDK·API 키·백엔드 위치 전송을 추가하지 않는다.
- `.transit` 경로가 없거나 시간 상한을 넘으면 결과에서 제외한다.
- fixture 결과를 실시간 실패 시 자동 대체하지 않는다.
- Apple이 제공하지 않는 도착시각·혼잡도·요금·환승 보장을 만들지 않는다.

---

### Task 1: 현재 위치 출발점 서비스

**Files:**
- Create: `apps/eodigaji-ios/Eodigaji/OriginLocation.swift`
- Create: `apps/eodigaji-ios/Eodigaji/LocationService.swift`
- Create: `apps/eodigaji-ios/EodigajiTests/LocationServiceTests.swift`
- Modify: `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`

**Interfaces:** Produces `OriginLocation(name:coordinate:source:)` and `LocationServicing.requestCurrentLocation() async throws -> OriginLocation`.

- [ ] **Step 1: Write failing XCTest for current-device origin and denied-permission error.**

```swift
func testCurrentLocationReturnsCurrentDeviceOrigin() async throws {
    let result = try await StubLocationService.current.requestCurrentLocation()
    XCTAssertEqual(result.source, .currentDevice)
}
```

- [ ] **Step 2: Run the focused test; expected failure: missing `OriginLocation` and `LocationServicing`.**
- [ ] **Step 3: Implement the protocol and a `CLLocationManager` adapter; request `.whenInUse` authorization and return only a device-local coordinate.**
- [ ] **Step 4: Run focused test; expected pass.**
- [ ] **Step 5: Commit `feat: add current location origin service`.**

### Task 2: 출발지 검색과 지도 핀 선택

**Files:**
- Create: `apps/eodigaji-ios/Eodigaji/OriginSearchService.swift`
- Create: `apps/eodigaji-ios/Eodigaji/OriginPickerView.swift`
- Create: `apps/eodigaji-ios/EodigajiTests/OriginSearchServiceTests.swift`
- Modify: `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`

**Interfaces:** Consumes Task 1 `OriginLocation`; produces `OriginSearching.search(query:region:) async throws -> [OriginLocation]` and `OriginPickerView(initialOrigin:onSelect:)`.

- [ ] **Step 1: Write failing test mapping a local-search result for `모현 한국외대` to a non-empty named coordinate origin.**
- [ ] **Step 2: Run focused test; expected failure: missing search service.**
- [ ] **Step 3: Implement `MKLocalSearch` adapter and `Map` annotation picker that returns selected pin coordinate.**
- [ ] **Step 4: Run test and build; manually confirm the picker callback receives a pin coordinate.**
- [ ] **Step 5: Commit `feat: add searchable map origin picker`.**

### Task 3: 실시간 대중교통 추천 서비스

**Files:**
- Create: `apps/eodigaji-ios/Eodigaji/LiveRecommendationService.swift`
- Create: `apps/eodigaji-ios/EodigajiTests/LiveRecommendationServiceTests.swift`
- Modify: `apps/eodigaji-ios/Eodigaji/APIModels.swift`
- Modify: `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`

**Interfaces:** Consumes `OriginLocation`, `Purpose`, `MaxTravelTimeMinutes`; produces `LiveRecommendation` and `LiveRecommendationServicing.recommend(from:purpose:maxTravelTime:) async throws -> [LiveRecommendation]`.

- [ ] **Step 1: Write failing tests for transit-only routing, inclusive time threshold, and origin-dependent local-search region.**

```swift
func testTransitRoutesOverLimitAreExcluded() async throws {
    let results = try await service.recommend(from: origin, purpose: .cafe, maxTravelTime: .thirty)
    XCTAssertEqual(results.map(\.placeName), ["가까운 카페"])
}
```

- [ ] **Step 2: Run focused test; expected failure: missing live service.**
- [ ] **Step 3: Implement purpose query mapping, `MKLocalSearch`, `.transit` `MKDirections`, route-step conversion, and stable sort by time/name.**
- [ ] **Step 4: Run all live-service tests; expected pass without a network dependency by stubbing search/directions ports.**
- [ ] **Step 5: Commit `feat: add live transit recommendation service`.**

### Task 4: 실시간 화면·상세 경로·Maps 열기

**Files:**
- Modify: `apps/eodigaji-ios/Eodigaji/RecommendationViewModel.swift`
- Modify: `apps/eodigaji-ios/Eodigaji/ContentView.swift`
- Create: `apps/eodigaji-ios/Eodigaji/LiveRecommendationDetailView.swift`
- Modify: `apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift`
- Create: `apps/eodigaji-ios/EodigajiTests/LiveRecommendationDetailTests.swift`
- Modify: `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`

**Interfaces:** Consumes Tasks 1–3; view model exposes `selectedOrigin`, `liveResults`, `liveError`, `recommendLive()`, and `dismissResults()`.

- [ ] **Step 1: Write failing test that selected map origin is passed to live service and generated Maps link uses source and destination coordinates.**
- [ ] **Step 2: Run focused test; expected failure: missing live state/method.**
- [ ] **Step 3: Add current-location control, search sheet, pin picker, loading/error states, route-step cards, and Apple Maps opener.**

```swift
MKMapItem.openMaps(with: [sourceItem, destinationItem], launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeTransit])
```

- [ ] **Step 4: Run all iOS XCTest and Simulator build; expected pass.**
- [ ] **Step 5: Commit `feat: show live map transit recommendations`.**

### Task 5: Simulator end-to-end verification

**Files:** Modify only a missing deterministic XCTest assertion if verification exposes it.

- [ ] **Step 1: Run `xcodebuild test` against concrete iPhone 17 Pro Simulator.**
- [ ] **Step 2: Install and launch app; exercise current location, `모현 한국외대` search, map pin, and live route.**
- [ ] **Step 3: Confirm changed origin changes search region; verify no transit route is fabricated.**
- [ ] **Step 4: Run `git diff --check` and inspect all changed paths.**
- [ ] **Step 5: Commit only any verification-test change; otherwise report no code change.**
