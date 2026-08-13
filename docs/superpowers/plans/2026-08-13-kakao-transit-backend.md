# Kakao Transit Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카카오 장소·대중교통 API를 FastAPI 뒤에서 호출하고 iOS 실시간 추천을 국내 좌표·카카오 경로 기준으로 전환한다.

**Architecture:** `KakaoClient`는 키 인증과 외부 HTTP를 단독 소유한다. `KakaoTransitRecommendationService`는 국내 좌표 검증, 목적별 장소 검색, 최대 4개 동시 대중교통 경로 계산과 필터링을 담당한다. iOS는 키 없이 새 백엔드 계약만 호출한다.

**Tech Stack:** FastAPI, Pydantic, httpx, pytest, SwiftUI, URLSession

## Global Constraints

- `KAKAO_REST_API_KEY`는 백엔드 `.env`에서만 읽고 로그·응답·iOS에 노출하지 않는다.
- 카카오 호출의 Authorization은 정확히 `KakaoAK <REST_API_KEY>`다.
- 국내 범위 밖 좌표는 외부 호출 전에 422로 거절한다.
- 카카오 대중교통 경로가 없거나 제한시간을 넘으면 제외하며 fixture/다른 이동수단으로 대체하지 않는다.
- 테스트는 httpx/URLSession stub을 쓰며 실제 키·네트워크를 사용하지 않는다.

---

### Task 1: 카카오 외부 API 클라이언트와 백엔드 도메인

**Files:**
- Create: `services/recommendation-api/app/kakao_client.py`
- Create: `services/recommendation-api/app/live_models.py`
- Create: `services/recommendation-api/app/live_service.py`
- Create: `services/recommendation-api/tests/test_kakao_live_service.py`
- Modify: `services/recommendation-api/requirements.txt`

**Interfaces:** Produces `KakaoClient.search_places()`, `KakaoClient.public_transit_route()`, and `KakaoTransitRecommendationService.recommend(request) -> LiveRecommendationResponse`.

- [ ] **Step 1: Write failing pytest cases for `KakaoAK` header, cafe keyword request, domestic-coordinate rejection, 30-minute inclusive filter, >30/no-route exclusion, and no fixture fallback.**

```python
def test_over_limit_and_missing_transit_routes_are_excluded(client_stub):
    result = service.recommend(valid_request(max_travel_time_minutes=30))
    assert [item.name for item in result.recommendations] == ["30분 카페"]
```

- [ ] **Step 2: Run focused pytest; expected import failure for missing live modules.**
- [ ] **Step 3: Add Pydantic request/response models and an injected `httpx.AsyncClient` adapter. Use `/v2/local/search/keyword.json` and `/v2/routing/publictraffic`; retain only provider-supplied duration/distance/steps.**
- [ ] **Step 4: Run focused and complete Python tests; expected pass without network.**
- [ ] **Step 5: Commit `feat: add Kakao transit recommendation domain`.**

### Task 2: FastAPI live endpoint and configuration safety

**Files:**
- Modify: `services/recommendation-api/app/main.py`
- Create: `services/recommendation-api/tests/test_live_http_api.py`
- Modify: `services/recommendation-api/app/kakao_client.py`

**Interfaces:** Produces `POST /v1/live-recommendations`; consumes Task 1 `LiveRecommendationRequest` and returns `LiveRecommendationResponse`.

- [ ] **Step 1: Write failing HTTP tests for 200 success, 422 outside-Korea coordinates, missing-key configuration failure without secret text, and provider 429/5xx mapping.**
- [ ] **Step 2: Run focused pytest; expected 404 or missing endpoint.**
- [ ] **Step 3: Register dependency construction from environment, map safe domain exceptions to HTTP responses, and keep existing fixture endpoint unchanged.**
- [ ] **Step 4: Run all Python tests and `git diff --check`; expected pass.**
- [ ] **Step 5: Perform a one-request smoke test using `.env`; report only status/provider/result count, never key. Commit `feat: expose Kakao live recommendation API`.**

### Task 3: iOS live API contract and client switch

**Files:**
- Modify: `apps/eodigaji-ios/Eodigaji/APIModels.swift`
- Create: `apps/eodigaji-ios/Eodigaji/KakaoLiveRecommendationAPIClient.swift`
- Modify: `apps/eodigaji-ios/Eodigaji/RecommendationViewModel.swift`
- Modify: `apps/eodigaji-ios/Eodigaji/EodigajiApp.swift`
- Modify: `apps/eodigaji-ios/Eodigaji.xcodeproj/project.pbxproj`
- Create: `apps/eodigaji-ios/EodigajiTests/KakaoLiveRecommendationAPIClientTests.swift`
- Modify: `apps/eodigaji-ios/EodigajiTests/RecommendationViewModelTests.swift`

**Interfaces:** Produces `KakaoLiveRecommendationServicing.recommend(from:purpose:maxTravelTime:)`; consumes backend `/v1/live-recommendations` and maps it to existing `LiveRecommendation` UI data.

- [ ] **Step 1: Write failing XCTest for snake_case request coordinates, response mapping to route cards, backend 422/provider errors, and no MapKit/fixture fallback.**
- [ ] **Step 2: Run focused test; expected missing client/protocol.**
- [ ] **Step 3: Implement URLSession client using existing localhost configuration; make it the production `ContentView` service while retaining MapKit location/search/pin UI.**
- [ ] **Step 4: Run all XCTest and simulator build; expected pass.**
- [ ] **Step 5: Commit `feat: use Kakao transit results in iOS`.**

### Task 4: Concrete Simulator integration verification

**Files:** Modify only missing deterministic test assertions if discovered.

- [ ] **Step 1: Start FastAPI with `.env`, then call `/healthz` and one Korean 30-minute cafe request; confirm key is not printed.**
- [ ] **Step 2: Build/install iOS app on iPhone 17 Pro Simulator. Search `모현 한국외대`, select it, choose 30 minutes and cafe, and request results.**
- [ ] **Step 3: Verify non-Korean stale map pin produces validation guidance instead of unrelated candidates.**
- [ ] **Step 4: Run full Python pytest, iOS XCTest, `git diff --check`, and inspect change scope.**
- [ ] **Step 5: Commit only verification-test changes; otherwise report no code change.**
