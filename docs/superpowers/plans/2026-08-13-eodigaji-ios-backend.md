# 어디가지 iOS 및 추천 API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 목적·대중교통 조건에 따라 달라지는 F0-public-rule 추천을 SwiftUI 앱과 FastAPI 서비스로 제공하고 iOS Simulator에서 검증한다.

**Architecture:** FastAPI는 fixture TransitProvider와 결정적 하드 필터/랭킹 규칙을 소유한다. SwiftUI 앱은 조건을 보내고 투명성 메타데이터를 포함한 결과를 표시한다. 실제 교통 API·제한 데이터는 연결하지 않는다.

**Tech Stack:** SwiftUI, XCTest, Python 3, FastAPI, Pydantic, pytest, Xcode Simulator.

## Global Constraints

- 모든 응답·화면에서 fixture 및 F0-public-rule을 표시한다.
- 대중교통 fixture 외 다른 이동수단을 자동 대체하지 않는다.
- 경로 없음·시간 미검증·최대 시간 초과는 랭킹 전에 제외한다.
- 결과는 최대 5개이며 비용 누락을 숫자로 만들지 않는다.
- 실제 교통 API, API 키, B078/B079, ML, 로그인, DB는 범위 밖이다.

---

## File Structure

- `services/recommendation-api/app/models.py`: 요청·응답 Pydantic 모델.
- `services/recommendation-api/app/repository.py`: 목적별 명시적 fixture 후보.
- `services/recommendation-api/app/service.py`: 입력 검증, 하드 필터, fallback 랭킹.
- `services/recommendation-api/app/main.py`: HTTP API와 한국어 오류 응답.
- `services/recommendation-api/tests/test_recommendations.py`: API 규칙 회귀 테스트.
- `apps/eodigaji-ios/EodigajiApp/*.swift`: SwiftUI 앱·API 클라이언트·화면 모델·뷰.
- `apps/eodigaji-ios/EodigajiAppTests/*.swift`: 디코딩·상태·목적 전달 테스트.

### Task 1: FastAPI 추천 도메인과 실패 테스트

**Files:**
- Create: `services/recommendation-api/requirements.txt`
- Create: `services/recommendation-api/app/models.py`
- Create: `services/recommendation-api/app/repository.py`
- Create: `services/recommendation-api/app/service.py`
- Create: `services/recommendation-api/tests/test_recommendations.py`

**Interfaces:**
- Produces: `RecommendationRequest`, `RecommendationResponse`, `recommend(request)`.

- [ ] **Step 1: 실패 테스트를 작성한다.**

```python
def test_cafe_and_food_have_different_first_destination():
    assert recommend(food_request).recommendations[0].name != recommend(cafe_request).recommendations[0].name

def test_over_limit_candidate_is_not_returned():
    assert all(item.journey_time_minutes <= 30 for item in recommend(request).recommendations)
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `pytest tests/test_recommendations.py -q`

Expected: FAIL because module/function is absent.

- [ ] **Step 3: 최소 fixture·하드 필터·목적별 순위를 구현한다.**

```python
eligible = [c for c in candidates if c.route_verified and c.time_verified and c.minutes <= request.max_travel_time_minutes]
ordered = sorted(eligible, key=lambda c: (profile.order.index(c.id), c.minutes, c.id))
return ordered[:5]
```

- [ ] **Step 4: 통과를 확인한다.**

Run: `pytest tests/test_recommendations.py -q`

Expected: PASS; fixture·F0-public-rule 메타데이터 포함.

- [ ] **Step 5: 커밋한다.**

```bash
git add services/recommendation-api
git commit -m "feat: add fixture recommendation domain"
```

### Task 2: FastAPI HTTP 계약과 검증

**Files:**
- Create: `services/recommendation-api/app/main.py`
- Modify: `services/recommendation-api/tests/test_recommendations.py`

**Interfaces:**
- Consumes: `recommend(RecommendationRequest)`.
- Produces: `POST /v1/recommendations` JSON API.

- [ ] **Step 1: HTTP 실패 테스트를 작성한다.**

```python
def test_invalid_transport_is_rejected(client):
    response = client.post('/v1/recommendations', json={**valid_payload, 'transport_mode': 'car'})
    assert response.status_code == 422
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `pytest tests/test_recommendations.py::test_invalid_transport_is_rejected -q`

Expected: FAIL because API does not exist.

- [ ] **Step 3: 라우트와 오류 번역을 구현한다.**

```python
@app.post('/v1/recommendations', response_model=RecommendationResponse)
def recommendations(request: RecommendationRequest) -> RecommendationResponse:
    return recommend(request)
```

- [ ] **Step 4: API 테스트를 실행한다.**

Run: `pytest -q`

Expected: PASS for invalid input, Top 5, 30분 경계, fixture labels.

- [ ] **Step 5: 커밋한다.**

```bash
git add services/recommendation-api
git commit -m "feat: expose recommendation API"
```

### Task 3: SwiftUI 앱 골격과 API 모델

**Files:**
- Create: `apps/eodigaji-ios/EodigajiApp.xcodeproj`
- Create: `apps/eodigaji-ios/EodigajiApp/AppConfig.swift`
- Create: `apps/eodigaji-ios/EodigajiApp/RecommendationModels.swift`
- Create: `apps/eodigaji-ios/EodigajiApp/RecommendationAPIClient.swift`
- Create: `apps/eodigaji-ios/EodigajiApp/EodigajiApp.swift`
- Create: `apps/eodigaji-ios/EodigajiAppTests/RecommendationModelsTests.swift`

**Interfaces:**
- Consumes: API response described in Task 2.
- Produces: `RecommendationAPIClient.fetch(request:) async throws -> RecommendationResponse`.

- [ ] **Step 1: JSON fixture 디코딩 실패 테스트를 작성한다.**

```swift
func testRecommendationResponseDecodesFixtureMetadata() throws {
  let response = try JSONDecoder().decode(RecommendationResponse.self, from: fixtureData)
  XCTAssertTrue(response.fixture)
  XCTAssertEqual(response.rankingBasis, "F0-public-rule")
}
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `xcodebuild test -project apps/eodigaji-ios/EodigajiApp.xcodeproj -scheme EodigajiApp -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: FAIL until models exist.

- [ ] **Step 3: Codable 모델·URLSession 클라이언트·개발 base URL 구성을 구현한다.**

```swift
func fetch(request: RecommendationRequest) async throws -> RecommendationResponse {
  var urlRequest = URLRequest(url: config.baseURL.appending(path: "/v1/recommendations"))
  urlRequest.httpMethod = "POST"
  urlRequest.httpBody = try JSONEncoder().encode(request)
  let (data, response) = try await URLSession.shared.data(for: urlRequest)
  guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw APIError.requestFailed }
  return try JSONDecoder().decode(RecommendationResponse.self, from: data)
}
```

- [ ] **Step 4: 테스트를 실행한다.**

Run: same `xcodebuild test` command.

Expected: PASS.

- [ ] **Step 5: 커밋한다.**

```bash
git add apps/eodigaji-ios
git commit -m "feat: add iOS API client foundation"
```

### Task 4: SwiftUI 조건 입력과 결과 화면

**Files:**
- Create: `apps/eodigaji-ios/EodigajiApp/RecommendationViewModel.swift`
- Create: `apps/eodigaji-ios/EodigajiApp/ContentView.swift`
- Create: `apps/eodigaji-ios/EodigajiApp/ResultsView.swift`
- Modify: `apps/eodigaji-ios/EodigajiAppTests/RecommendationModelsTests.swift`

**Interfaces:**
- Consumes: `RecommendationAPIClient.fetch(request:)`.
- Produces: `RecommendationViewModel.search()` and visible loading/error/result states.

- [ ] **Step 1: 목적 전달과 오류 상태 테스트를 작성한다.**

```swift
func testSearchUsesSelectedPurpose() async {
  let client = RecordingClient()
  let model = RecommendationViewModel(client: client)
  model.purpose = .cafe
  await model.search()
  XCTAssertEqual(client.lastRequest?.purpose, .cafe)
}
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `xcodebuild test -project apps/eodigaji-ios/EodigajiApp.xcodeproj -scheme EodigajiApp -destination 'platform=iOS Simulator,name=iPhone 16'`

Expected: FAIL until ViewModel exists.

- [ ] **Step 3: 입력·결과·근거·정보 UI를 구현한다.**

```swift
Picker("목적", selection: $viewModel.purpose) { ForEach(Purpose.allCases) { Text($0.label) } }
Button("추천 보기") { Task { await viewModel.search() } }
```

- [ ] **Step 4: 투명성·빈·오류 상태를 구현한다.**

```swift
Text("공개 데이터 규칙 기반 · 데모 fixture · 실시간 정보 아님")
```

- [ ] **Step 5: 테스트와 빌드를 실행한다.**

Run: `xcodebuild test ...` and `xcodebuild build ...`

Expected: PASS.

- [ ] **Step 6: 커밋한다.**

```bash
git add apps/eodigaji-ios
git commit -m "feat: add iOS recommendation flow"
```

### Task 5: 로컬 통합 및 Simulator 검수

**Files:**
- Modify: `services/recommendation-api/README.md`
- Modify: `apps/eodigaji-ios/EodigajiApp/AppConfig.swift`

**Interfaces:**
- Consumes: backend running at configured development URL.

- [ ] **Step 1: API를 로컬에서 실행한다.**

Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

Expected: health and recommendation route respond.

- [ ] **Step 2: Simulator용 base URL을 실제 확인된 호스트 주소로 설정한다.**

```swift
static let developmentBaseURL = URL(string: "http://127.0.0.1:8000")!
```

- [ ] **Step 3: Simulator에 설치하고 핵심 흐름을 수행한다.**

Run: `xcrun simctl boot <device-id>` then `xcodebuild test` and `xcrun simctl launch <device-id> <bundle-id>`.

Expected: 회기 출발, 대중교통, 30분, 식사와 카페를 바꾸면 1위·근거·목적 요약이 달라진다.

- [ ] **Step 4: 검사와 커밋을 수행한다.**

Run: `pytest -q`, `xcodebuild test ...`, `git diff --check`.

Expected: all pass; no live-data/ML claims.

- [ ] **Step 5: 커밋한다.**

```bash
git add apps/eodigaji-ios services/recommendation-api
git commit -m "test: verify iOS and API integration"
```
