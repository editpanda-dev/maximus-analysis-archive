# Task 3 report — iOS Kakao live client switch

## Evidence

- TDD red: focused `KakaoLiveRecommendationAPIClientTests` initially failed because
  `KakaoLiveRecommendationAPIClient` and its error type did not exist.
- Focused XCTest: `KakaoLiveRecommendationAPIClientTests` and
  `RecommendationViewModelTests` passed on the configured iPhone 17 Pro simulator.
- Full XCTest: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,name=iPhone 17 Pro' CODE_SIGNING_ALLOWED=NO` passed.
- Simulator build: the equivalent `xcodebuild build` command passed.
- Whitespace: `git diff --check` passed.

## Changed files

- `apps/eodigaji-ios/Eodigaji/APIModels.swift`
- `apps/eodigaji-ios/Eodigaji/KakaoLiveRecommendationAPIClient.swift`
- `apps/eodigaji-ios/Eodigaji/ContentView.swift`
- `apps/eodigaji-ios/Eodigaji/EodigajiApp.swift`
- `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`
- `apps/eodigaji-ios/EodigajiTests/KakaoLiveRecommendationAPIClientTests.swift`
- `apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift`

## Contract and safety

`KakaoLiveRecommendationAPIClient` posts `origin_name`, `origin_latitude`,
`origin_longitude`, `purpose`, and `max_travel_time_minutes` to
`/v1/live-recommendations`, then maps backend route cards into the existing
`LiveRecommendation` UI model. It maps backend 422/provider failures to safe
messages and does not invoke MapKit directions, the legacy fixture endpoint,
or any fallback result path.

`ContentView` now uses this live backend client in production. MapKit remains
only for device location, origin search, and manual pin selection. The iOS
source and project configuration contain no Kakao REST key, key environment
read, or authorization header.
