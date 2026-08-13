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
- `apps/eodigaji-ios/Eodigaji/LiveRecommendationDetailView.swift`
- `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`
- `apps/eodigaji-ios/EodigajiTests/KakaoLiveRecommendationAPIClientTests.swift`
- `apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift`
- Deleted obsolete MapKit recommendation implementation and its XCTest file:
  `LiveRecommendationService.swift` and `LiveRecommendationServiceTests.swift`.

## Contract and safety

`KakaoLiveRecommendationAPIClient` posts `origin_name`, `origin_latitude`,
`origin_longitude`, `purpose`, and `max_travel_time_minutes` to
`/v1/live-recommendations`, then maps Kakao transit route cards into the
existing `LiveRecommendation` UI model. FastAPI's actual Pydantic 422
`detail` array is decoded into Korean domestic-origin guidance for both
model-level domestic-region validation and latitude/longitude range errors;
provider failures retain their safe backend message. No MapKit recommendation service, legacy fixture
endpoint, or fallback result path is compiled or wired.

`ContentView` now uses this live backend client in production. The UI explains
that selected coordinates go to the app's recommendation API and Kakao Map
services for place/transit-route search. MapKit remains for device location,
Apple place search, manual pin selection, and an optional Apple Maps location
link; it is not used for recommendation routing. The iOS source and project
configuration contain no Kakao REST key, key environment read, or
authorization header.
