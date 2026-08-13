# 정확한 행정동 코드 그룹화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 주소 문자열 추정을 없애고 카카오 좌표→행정구역의 행정동(H) 코드로 대중교통 점포를 정확히 그룹화한다.

**Architecture:** `KakaoClient`가 점포 좌표별 행정동 레코드를 조회한다. 서비스는 대중교통 시간 필터를 통과한 점포에만 이 조회를 적용하고, 행정동 코드로 묶어 기존 동네 API 응답을 만든다. iOS 응답 형식은 바뀌지 않는다.

**Tech Stack:** FastAPI, Pydantic, httpx, pytest, SwiftUI, URLSession, XCTest

## Global Constraints

- `KAKAO_REST_API_KEY`는 백엔드 `.env`에서만 읽고 로그·응답·iOS에 노출하지 않는다.
- 카카오 호출의 Authorization은 정확히 `KakaoAK <REST_API_KEY>`다.
- 행정동 조회는 `GET https://dapi.kakao.com/v2/local/geo/coord2regioncode.json`에 점포 `x`·`y` 좌표를 넣어 호출한다.
- 응답 중 `region_type == "H"`만 행정동으로 인정하며, `code`를 그룹 식별자로, `region_3depth_name`을 표시명으로 쓴다.
- `B` 법정동 또는 주소 문자열로 행정동을 추정하지 않는다. `H` 레코드가 없으면 해당 점포는 동네 추천에서 제외한다.
- 서로 다른 행정동 코드는 표시명이 같아도 절대 병합하지 않는다.
- 대중교통 경로가 없거나 제한시간을 넘으면 행정동 조회 전에 제외한다.
- 행정동은 최소 소요시간, 점포 수 내림차순, 최소 거리, 가나다순으로 정렬하며 최대 5개만 반환한다.
- 테스트는 httpx stub을 쓰며 실제 키·네트워크를 사용하지 않는다.

---

### Task 1: 카카오 행정동 조회 어댑터와 코드 기반 그룹화

**Files:**
- Modify: `services/recommendation-api/app/kakao_client.py`
- Modify: `services/recommendation-api/app/live_models.py`
- Replace: `services/recommendation-api/app/district_service.py`
- Modify: `services/recommendation-api/tests/test_kakao_live_service.py`
- Modify: `services/recommendation-api/tests/test_district_service.py`

**Interfaces:**
- Produces `KakaoAdministrativeDistrict(code: str, name: str)`.
- Produces `KakaoClient.administrative_district(longitude: float, latitude: float) async -> KakaoAdministrativeDistrict | None`.
- Produces `DistrictCandidate(district_code: str, district_name: str, place: LiveRecommendation)` and `build_district_recommendations(candidates: list[DistrictCandidate], maximum_districts: int = 5) -> list[DistrictRecommendation]`.

- [ ] **Step 1: Write failing adapter and code-group tests.**

```python
async def test_reads_only_h_administrative_district_from_coordinate_response(client):
    district = await client.administrative_district(longitude=127.1, latitude=37.5)
    assert district == KakaoAdministrativeDistrict(code="1168065000", name="신사동")

def test_same_display_name_with_different_h_codes_stays_separate():
    groups = build_district_recommendations([
        candidate("1168065000", "신사동", place("강남카페", duration=600)),
        candidate("1162058500", "신사동", place("관악카페", duration=610)),
    ])
    assert [group.place_count for group in groups] == [1, 1]
    assert len(groups) == 2
```

Include fixtures with both a `B` record and an `H` record; prove the `H` record is selected. Add a no-`H` case returning `None`, and prove a candidate without a district is excluded.

- [ ] **Step 2: Run focused tests and confirm the missing adapter/code-based inputs fail.**

Run: `python3 -m pytest -q tests/test_kakao_live_service.py tests/test_district_service.py`

- [ ] **Step 3: Implement the provider adapter and code-keyed grouping.**

```python
async def administrative_district(
    self, *, longitude: float, latitude: float
) -> KakaoAdministrativeDistrict | None:
    response = await self._http_client.get(
        f"{self._local_api_base_url}/v2/local/geo/coord2regioncode.json",
        headers=self._headers,
        params={"x": longitude, "y": latitude},
    )
    self._raise_for_provider_error(response)
    record = next((item for item in response.json()["documents"] if item.get("region_type") == "H"), None)
    if record is None:
        return None
    return KakaoAdministrativeDistrict(code=str(record["code"]), name=str(record["region_3depth_name"]))
```

Delete address-token parsing from `district_service.py`. Group dictionary keys must be `district_code`, not display names. Keep display names and place sorting exactly as the current API contract expects.

- [ ] **Step 4: Add concurrency/cap regression tests.**

```python
def test_group_cap_cannot_exceed_five_when_codes_are_distinct():
    assert len(build_district_recommendations(six_code_distinct_candidates(), maximum_districts=99)) == 5
```

- [ ] **Step 5: Run focused and complete backend tests.**

Run: `python3 -m pytest -q tests/test_kakao_live_service.py tests/test_district_service.py && python3 -m pytest -q && git diff --check`

- [ ] **Step 6: Commit adapter/grouping changes.**

```bash
git add services/recommendation-api/app/kakao_client.py services/recommendation-api/app/live_models.py services/recommendation-api/app/district_service.py services/recommendation-api/tests/test_kakao_live_service.py services/recommendation-api/tests/test_district_service.py
git commit -m "fix: group districts by Kakao administrative code"
```

### Task 2: 동네 추천 서비스 통합과 실제 검증

**Files:**
- Modify: `services/recommendation-api/app/live_service.py`
- Modify: `services/recommendation-api/tests/test_district_http_api.py`
- Modify only deterministic backend tests required by the integration.

**Interfaces:**
- Consumes `KakaoClient.administrative_district()` and Task 1 code-keyed candidates.
- Preserves `POST /v1/live-district-recommendations` response shape and iOS compatibility.

- [ ] **Step 1: Write failing service tests proving only route-eligible places resolve a district and missing H excludes a place.**

```python
async def test_district_lookup_is_not_called_for_over_limit_or_no_route_places():
    response = await service.recommend_districts(valid_request(max_travel_time_minutes=30))
    assert client.district_lookup_coordinates == [(127.254, 37.335)]
    assert response.districts[0].places[0].place_name == "30분 카페"
```

- [ ] **Step 2: Run the focused tests and confirm they fail before service integration.**

Run: `python3 -m pytest -q tests/test_district_http_api.py tests/test_kakao_live_service.py`

- [ ] **Step 3: Resolve H districts after transit filtering, with a maximum of four concurrent external requests.**

```python
district = await self._client.administrative_district(
    longitude=recommendation.destination_longitude,
    latitude=recommendation.destination_latitude,
)
if district is not None:
    candidates.append(DistrictCandidate(
        district_code=district.code,
        district_name=district.name,
        place=recommendation,
    ))
```

Use a semaphore clamped to four for district lookups too; translate provider errors through the existing HTTP boundary. The existing direct-place endpoint must not perform district lookups.

- [ ] **Step 4: Add HTTP regression tests for duplicate display names with different codes and provider-error safety.**

```python
def test_live_district_endpoint_returns_two_same_named_cards_for_two_codes(client, service_stub):
    payload = client.post("/v1/live-district-recommendations", json=valid_payload()).json()
    assert [item["district_name"] for item in payload["districts"]] == ["신사동", "신사동"]
    assert [item["place_count"] for item in payload["districts"]] == [1, 1]
```

- [ ] **Step 5: Run full backend verification.**

Run: `python3 -m pytest -q && git diff --check`

- [ ] **Step 6: Perform actual Kakao smoke verification only in the configured parent workspace.**

Start the parent FastAPI service from its existing `.env`; POST `한국외국어대학교 글로벌캠퍼스` (`37.3375,127.2642`), `cafe`, `30` to `/v1/live-district-recommendations`; report only HTTP status, provider, fixture flag, district display/count, and no key. Confirm returned card name comes from the `H` record. Stop the server afterward.

- [ ] **Step 7: Commit service integration.**

```bash
git add services/recommendation-api/app/live_service.py services/recommendation-api/tests/test_district_http_api.py services/recommendation-api/tests/test_kakao_live_service.py
git commit -m "fix: resolve district cards from Kakao H regions"
```

## Self-review

- Spec coverage: Task 1 replaces string inference with Kakao H-code identity; Task 2 ensures only eligible points are resolved, preserves the endpoint/iOS shape, and verifies the real provider.
- No-placeholder scan: completed; all calls, response fields, and test behavior are explicit.
- Type consistency: the client produces `KakaoAdministrativeDistrict`; the service constructs `DistrictCandidate`; the grouper produces the existing `DistrictRecommendation` response model.
