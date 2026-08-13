# 행정동 우선 추천 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카카오 대중교통 기준으로 행정동을 먼저 추천하고, 선택한 행정동의 실제 점포·경로를 이어서 보여준다.

**Architecture:** FastAPI는 기존 장소·대중교통 후보를 행정동으로 안전하게 그룹화해 새 전용 API로 반환한다. iOS는 새 클라이언트와 뷰모델 상태를 통해 동네 카드 화면과 해당 동네 점포 목록 화면을 분리한다. 클릭 뒤에는 추가 카카오 호출 없이 최초 응답의 점포만 사용한다.

**Tech Stack:** FastAPI, Pydantic, httpx, pytest, SwiftUI, URLSession, XCTest

## Global Constraints

- `KAKAO_REST_API_KEY`는 백엔드 `.env`에서만 읽고 로그·응답·iOS에 노출하지 않는다.
- 카카오 호출의 Authorization은 정확히 `KakaoAK <REST_API_KEY>`다.
- 국내 범위 밖 좌표는 외부 호출 전에 422로 거절한다.
- 카카오 대중교통 경로가 없거나 제한시간을 넘으면 제외하며 fixture/다른 이동수단으로 대체하지 않는다.
- 행정동은 주소에서 신뢰성 있게 추출할 수 있을 때만 사용하며, 불명확한 주소는 추정하지 않고 제외한다.
- 행정동은 최소 소요시간, 점포 수 내림차순, 최소 거리, 가나다순으로 정렬하며 최대 5개만 반환한다.
- 동네 상세는 최초 응답의 해당 행정동 점포만 표시하며 추가 카카오 호출을 하지 않는다.
- 테스트는 httpx/URLSession stub을 쓰며 실제 키·네트워크를 사용하지 않는다.

---

### Task 1: 서버 행정동 추출·그룹화 도메인

**Files:**
- Create: `services/recommendation-api/app/district_service.py`
- Modify: `services/recommendation-api/app/live_models.py`
- Modify: `services/recommendation-api/tests/test_kakao_live_service.py`
- Create: `services/recommendation-api/tests/test_district_service.py`

**Interfaces:**
- Produces `extract_administrative_district(address: str) -> str | None`.
- Produces `DistrictRecommendation` with `district_name`, `fastest_travel_time_seconds`, `place_count`, `places`.
- Produces `build_district_recommendations(places: list[LiveRecommendation], maximum_districts: int = 5) -> list[DistrictRecommendation]`.

- [ ] **Step 1: Write failing parsing and grouping tests.**

```python
def test_groups_mohyeon_eup_places_and_orders_by_fastest_then_count():
    districts = build_district_recommendations([
        place("썸카페", "경기 용인시 처인구 모현읍 외대로 42-1", 547, 1194),
        place("이디야", "경기 용인시 처인구 모현읍 외대로 36", 552, 1202),
        place("죽전카페", "경기 용인시 수지구 죽전동 123", 540, 1400),
    ])
    assert [district.district_name for district in districts] == ["죽전동", "모현읍"]
    assert districts[1].place_count == 2

def test_unparseable_address_is_not_assigned_to_a_district():
    assert extract_administrative_district("주소 정보 없음") is None
```

- [ ] **Step 2: Run the focused tests and confirm they fail because the module/types do not exist.**

Run: `python3 -m pytest -q tests/test_district_service.py`

- [ ] **Step 3: Add the minimal explicit Korean address parser and group types.**

```python
DISTRICT_SUFFIXES = ("읍", "면", "동")

def extract_administrative_district(address: str) -> str | None:
    for token in address.split():
        if token.endswith(DISTRICT_SUFFIXES) and len(token) > 1:
            return token
    return None
```

Create groups only for non-empty parsed district names; sort places by duration/distance/name and groups by `(fastest_duration, -place_count, fastest_distance, district_name)`; cap using `min(5, max(1, maximum_districts))`.

- [ ] **Step 4: Add boundary tests for 5-district cap, distance/name tie-breakers, and places within a group.**

```python
def test_group_cap_cannot_be_overridden_above_five():
    districts = build_district_recommendations(six_distinct_places(), maximum_districts=99)
    assert len(districts) == 5
```

- [ ] **Step 5: Run focused and full backend tests.**

Run: `python3 -m pytest -q tests/test_district_service.py && python3 -m pytest -q`
Expected: all pass without network.

- [ ] **Step 6: Commit the domain change.**

```bash
git add services/recommendation-api/app/district_service.py services/recommendation-api/app/live_models.py services/recommendation-api/tests/test_district_service.py services/recommendation-api/tests/test_kakao_live_service.py
git commit -m "feat: group transit candidates by district"
```

### Task 2: 행정동 추천 HTTP 계약

**Files:**
- Modify: `services/recommendation-api/app/live_service.py`
- Modify: `services/recommendation-api/app/main.py`
- Create: `services/recommendation-api/tests/test_district_http_api.py`

**Interfaces:**
- Consumes `LiveRecommendationRequest` and `KakaoTransitRecommendationService` candidate generation.
- Produces `KakaoTransitRecommendationService.recommend_districts(request) -> LiveDistrictRecommendationResponse`.
- Produces `POST /v1/live-district-recommendations`.

- [ ] **Step 1: Write failing endpoint tests for a grouped 200 response, empty candidates, outside-Korea 422 before key construction, and provider 429/5xx mapping.**

```python
def test_live_district_endpoint_returns_grouped_kakao_only_response(client, service_stub):
    response = client.post("/v1/live-district-recommendations", json=valid_payload())
    assert response.status_code == 200
    assert response.json()["fixture"] is False
    assert response.json()["districts"][0]["district_name"] == "모현읍"

def test_foreign_origin_is_422_even_without_a_kakao_key(client, monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    assert client.post("/v1/live-district-recommendations", json=foreign_payload()).status_code == 422
```

- [ ] **Step 2: Run focused endpoint tests and confirm the endpoint is absent.**

Run: `python3 -m pytest -q tests/test_district_http_api.py`

- [ ] **Step 3: Refactor candidate selection once, then add the district response method and route.**

```python
async def recommend_districts(
    self, request: LiveRecommendationRequest
) -> LiveDistrictRecommendationResponse:
    eligible = await self._eligible_recommendations(request)
    districts = build_district_recommendations(eligible)
    return LiveDistrictRecommendationResponse(
        result_status="ok" if districts else "no_eligible_candidates",
        queried_at=datetime.now(timezone.utc),
        eligible_count=len(eligible), districts=districts, limitations=LIMITATIONS,
    )
```

Keep `recommend()` behavior unchanged by reusing `_eligible_recommendations`; expose the new route with the same safe provider-error translation as `/v1/live-recommendations`.

- [ ] **Step 4: Run focused and full backend verification.**

Run: `python3 -m pytest -q tests/test_district_http_api.py && python3 -m pytest -q && git diff --check`

- [ ] **Step 5: Commit the HTTP contract.**

```bash
git add services/recommendation-api/app/live_service.py services/recommendation-api/app/main.py services/recommendation-api/tests/test_district_http_api.py
git commit -m "feat: expose district-first transit recommendations"
```

### Task 3: iOS 행정동 API 모델·클라이언트

**Files:**
- Modify: `apps/eodigaji-ios/Eodigaji/APIModels.swift`
- Create: `apps/eodigaji-ios/Eodigaji/KakaoDistrictRecommendationAPIClient.swift`
- Create: `apps/eodigaji-ios/EodigajiTests/KakaoDistrictRecommendationAPIClientTests.swift`
- Modify: `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`

**Interfaces:**
- Produces `LiveDistrictRecommendation` with `districtName`, `fastestTravelTime`, `placeCount`, `places`.
- Produces `DistrictRecommendationServicing.recommendDistricts(from:purpose:maxTravelTime:) async throws -> [LiveDistrictRecommendation]`.
- Uses `POST /v1/live-district-recommendations` and existing `KakaoLiveRecommendationRequest`.

- [ ] **Step 1: Write failing URLProtocol tests for snake_case request encoding, a district/places response mapping, no eligible districts, and HTTP error propagation.**

```swift
func testMapsDistrictResponseAndRetainsOnlyItsPlaces() async throws {
    stub.responseData = districtResponse(district: "모현읍", places: ["썸카페", "이디야"])
    let districts = try await client.recommendDistricts(from: origin, purpose: .cafe, maxTravelTime: .thirty)
    XCTAssertEqual(districts.map(\.districtName), ["모현읍"])
    XCTAssertEqual(districts[0].places.map(\.placeName), ["썸카페", "이디야"])
}
```

- [ ] **Step 2: Run the focused XCTest and confirm it fails because the client/protocol is missing.**

Run: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' -only-testing:EodigajiTests/KakaoDistrictRecommendationAPIClientTests`

- [ ] **Step 3: Implement the isolated API client.**

```swift
@MainActor
public protocol DistrictRecommendationServicing: AnyObject {
    func recommendDistricts(
        from origin: OriginLocation,
        purpose: Purpose,
        maxTravelTime: MaxTravelTimeMinutes
    ) async throws -> [LiveDistrictRecommendation]
}
```

Reuse the current validation-error parser and backend error type; do not add any Kakao key/header to iOS. Add the new source/test file references to the Xcode project.

- [ ] **Step 4: Run focused XCTest, full XCTest, simulator build, and whitespace check.**

Run: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' && xcodebuild build -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' && git diff --check`

- [ ] **Step 5: Commit the iOS contract.**

```bash
git add apps/eodigaji-ios/Eodigaji/APIModels.swift apps/eodigaji-ios/Eodigaji/KakaoDistrictRecommendationAPIClient.swift apps/eodigaji-ios/EodigajiTests/KakaoDistrictRecommendationAPIClientTests.swift apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj
git commit -m "feat: add district recommendation API client"
```

### Task 4: iOS 동네 카드와 점포 상세 흐름

**Files:**
- Modify: `apps/eodigaji-ios/Eodigaji/RecommendationViewModel.swift`
- Modify: `apps/eodigaji-ios/Eodigaji/ContentView.swift`
- Modify: `apps/eodigaji-ios/Eodigaji/EodigajiApp.swift`
- Create: `apps/eodigaji-ios/EodigajiTests/DistrictRecommendationViewModelTests.swift`
- Modify: `apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift`

**Interfaces:**
- Consumes `DistrictRecommendationServicing` from Task 3.
- Produces `liveDistricts`, `selectedDistrict`, `recommendDistrictsLive()`, `selectDistrict(_:)`, and `dismissDistrictPlaces()` on `RecommendationViewModel`.
- UI shows district cards first and a detail list containing exactly `selectedDistrict.places`.

- [ ] **Step 1: Write failing view-model tests for district-first result state, selection isolation, back-state preservation, and no fallback on failure.**

```swift
func testSelectingDistrictShowsOnlyThatDistrictsExistingPlacesAndBackKeepsDistricts() async {
    await viewModel.recommendDistrictsLive()
    viewModel.selectDistrict(viewModel.liveDistricts[1])
    XCTAssertEqual(viewModel.selectedDistrict?.places.map(\.placeName), ["죽전카페"])
    viewModel.dismissDistrictPlaces()
    XCTAssertEqual(viewModel.liveDistricts.count, 2)
    XCTAssertNil(viewModel.selectedDistrict)
}
```

- [ ] **Step 2: Run focused XCTest and confirm the new state/actions are absent.**

Run: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' -only-testing:EodigajiTests/DistrictRecommendationViewModelTests`

- [ ] **Step 3: Add view-model state and wire production composition.**

```swift
@Published public private(set) var liveDistricts: [LiveDistrictRecommendation] = []
@Published public private(set) var selectedDistrict: LiveDistrictRecommendation?

public func selectDistrict(_ district: LiveDistrictRecommendation) {
    selectedDistrict = district
}

public func dismissDistrictPlaces() {
    selectedDistrict = nil
}
```

Make `recommendDistrictsLive()` clear stale district and place state, capture origin/purpose/time snapshots as the existing live request does, and retain candidates on back. `EodigajiApp` supplies `KakaoDistrictRecommendationAPIClient`; no MapKit or fixture recommendation fallback is added.

- [ ] **Step 4: Replace the result presentation with two explicit SwiftUI states.**

```swift
if let district = viewModel.selectedDistrict {
    DistrictPlaceListView(district: district, onBack: viewModel.dismissDistrictPlaces)
} else {
    DistrictRecommendationListView(districts: viewModel.liveDistricts, onSelect: viewModel.selectDistrict)
}
```

Each district card shows `districtName`, `ceil(fastestTravelTime / 60)` minutes, and `placeCount`. The detail list reuses `LiveRecommendationCard` and `LiveRecommendationDetailView`; its back button returns to the district cards.

- [ ] **Step 5: Run full XCTest, simulator build, install, and manual deterministic flow.**

Run: `xcodebuild test -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' && xcodebuild build -project apps/eodigaji-ios/Eodigaji.xcodeproj -scheme Eodigaji -destination 'platform=iOS Simulator,id=959C0327-D8C4-46E2-953C-7C83965C4079' && git diff --check`

Set simulator location to `37.3375,127.2642`, request a 30-minute cafe recommendation, verify district cards appear, select one, verify only its returned places appear, then return and verify cards remain.

- [ ] **Step 6: Commit the user flow.**

```bash
git add apps/eodigaji-ios/Eodigaji/RecommendationViewModel.swift apps/eodigaji-ios/Eodigaji/ContentView.swift apps/eodigaji-ios/Eodigaji/EodigajiApp.swift apps/eodigaji-ios/EodigajiTests/DistrictRecommendationViewModelTests.swift apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift
git commit -m "feat: show districts before place recommendations"
```

### Task 5: 실제 카카오 통합 검증

**Files:**
- Modify only deterministic tests discovered as necessary during verification.

**Interfaces:**
- Uses the API and UI contracts from Tasks 1-4.

- [ ] **Step 1: Start the FastAPI service with the existing local `.env` without printing its value.**

Run: `set -a; source .env; set +a; python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

- [ ] **Step 2: Verify a real Korean request returns only Kakao data.**

Run a `POST /v1/live-district-recommendations` for `한국외국어대학교 글로벌캠퍼스` at `37.3375,127.2642`, `cafe`, `30`; confirm HTTP 200, `provider: kakao`, `fixture: false`, at least one district, and each returned place belongs to its enclosing district.

- [ ] **Step 3: Verify a foreign origin returns 422 and does not produce unrelated candidates.**

Run a request with San Francisco coordinates; confirm HTTP 422 and no response exposes a key.

- [ ] **Step 4: Run all automated checks and inspect scope.**

Run: `python3 -m pytest -q`, full `xcodebuild test`, simulator build, `git diff --check`, and `git status --short`.

- [ ] **Step 5: Commit only a discovered deterministic test correction; otherwise record no code commit.**

Use `fix: verify district recommendation integration` only if a test artifact changes; otherwise report the live evidence and stop the local server.

## Self-review

- Spec coverage: Tasks 1-2 implement extraction, grouping, ordering, cap, no fallback, and HTTP safety; Tasks 3-4 implement iOS contract, cards, selection, back state, errors, and privacy-preserving boundary; Task 5 covers real Kakao and simulator behavior.
- No-placeholder scan: completed; each task includes concrete commands and target behavior.
- Type consistency: Task 1 produces `DistrictRecommendation`; Task 2 wraps it as `LiveDistrictRecommendationResponse`; Task 3 maps it to `LiveDistrictRecommendation`; Task 4 consumes that exact client protocol/state.
