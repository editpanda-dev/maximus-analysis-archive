# 막시무스(어디가지) 인수인계

작성일: 2026-08-17

## 1. 프로젝트 목적

**어디가지(Where Do We Go?)**는 사용자가 출발지, 방문 목적, 최대 이동시간을 입력하면 먼저 **행정동**을 추천하고, 동을 누르면 해당 동의 구체 점포와 대중교통 이동 단계를 보여주는 iOS MVP다.

- iOS 앱: `apps/eodigaji-ios/`
- FastAPI 백엔드: `services/recommendation-api/`
- 사업계획서 원본: `output/reports/HUFS_Start-up_Platform_막시무스_사업계획서.docx`
- 현재 앱 기본 출발지 흐름: 현재 위치 / 장소 검색 / 지도 핀 상세 위치
- 목적: 맛집, 카페, 데이트, 쇼핑, 문화, 휴식
- 시간 옵션: 20·30·40·60분

## 2. 가장 최근 사용자 피드백과 현재 장애

사용자는 시뮬레이터에서 **한국외대 서울캠퍼스 앞 → 맛집 → 30분**으로 입력했을 때 동 추천이 비어 있는 문제를 제보했다.

### 확인된 사실

1. 동 추천 API는 `POST /v1/live-district-recommendations`다.
2. 현재 설계는 “카카오 대중교통으로 실제 20–30분이 검증된 점포”만 행정동으로 그룹화한다. 따라서 검증 점포가 0개이면 동도 0개가 된다.
3. 조사 중 카카오 대중교통 API가 다음 응답을 반환했다.

```json
{"errorType":"BadRequest","message":"API limit has been exceeded.","code":-10}
```

4. 그래서 지금은 **실시간 대중교통 경로를 검증할 수 없다.** 앱이 ‘추천 없음’처럼 보이는 직접 원인이다.
5. 카카오 로컬 장소 검색은 동작했던 상태다. 즉, 동 우선 목록을 로컬 검색+행정동 역지오코딩으로 반환하는 보완은 가능하다.

### 다음 구현 권장안

사용자가 원한 UX는 “동 먼저 → 점포·상세 경로”다. 따라서 아래처럼 분리하는 것이 맞다.

1. 동 목록 API는 카카오 로컬 검색 결과와 행정동 역지오코딩으로 구성한다.
2. 동 카드는 `대중교통 경로 확인 중` 또는 `API 한도 초과로 경로 확인 불가` 상태를 명시한다.
3. 동을 누른 뒤 해당 동 점포에 대해서만 대중교통 경로를 조회한다.
4. 경로 API 한도 초과·429·`code=-10`은 ‘추천 없음’으로 삼키지 말고 명시적 오류로 전달한다.
5. 추정 이동시간을 보여야 한다면 반드시 `추정`이라고 표기하고 카카오 실시간/확정 경로인 것처럼 표시하지 않는다.

## 3. 현재 구현 상태

### 완료되어 커밋된 사항

최근 주요 커밋:

- `a40456e fix: recover pin recommendations and show route maps`
  - 상세 위치 핀은 탭만으로 닫히지 않고 `이 위치로 설정` 버튼으로 확정
  - 한 후보의 4xx 경로 오류가 전체 추천을 502로 실패시키지 않도록 처리
  - 카카오 응답의 `steps[].path.points`를 보존하여 상세 화면 지도에 표시
  - 지도 표기: 초록 출발지, 빨강 도착지, 주황 도보, 파랑 대중교통
- `f1f621a feat: recommend destinations in selected travel window`
  - 30분 선택 시 20–30분 구간을 목표로 필터링
- `c3cc638 fix: center origin map and recover nearby routes`
- `ca50941`, `8de6e97`
  - 홈/스플래시 진입 흐름

### 현재 미커밋 변경 — 안정 버전으로 취급하면 안 됨

다음 두 파일에 실험 중인 변경이 남아 있다.

- `services/recommendation-api/app/live_service.py`
- `services/recommendation-api/tests/test_kakao_live_service.py`

내용은 20–30분 후보 탐색 고리(ring)를 여러 거리·16방향으로 확대하려던 시도다. 이 변경은 아직 전체 테스트/커밋을 완료하지 않았고, 카카오 API 한도 초과 상태에서는 실제 검증도 불가능하다.

다음 작업자는 먼저 `git diff`로 내용을 검토한 뒤 다음 둘 중 하나를 택해야 한다.

- 위 ‘동 우선 API 분리’ 설계에 맞게 다시 구현한다.
- 필요 없으면 해당 두 파일의 미커밋 변경만 되돌린다. **사용자 소유의 다른 untracked 파일은 절대 건드리지 않는다.**

## 4. 핵심 코드 위치

| 책임 | 파일 |
|---|---|
| FastAPI 라우트와 오류 매핑 | `services/recommendation-api/app/main.py` |
| 카카오 Local/대중교통 어댑터 | `services/recommendation-api/app/kakao_client.py` |
| 후보 검색·시간 윈도우·행정동 그룹화 | `services/recommendation-api/app/live_service.py` |
| API 응답 모델 | `services/recommendation-api/app/live_models.py` |
| iOS 동 추천 HTTP 클라이언트 | `apps/eodigaji-ios/Eodigaji/KakaoDistrictRecommendationAPIClient.swift` |
| iOS 상태 관리 | `apps/eodigaji-ios/Eodigaji/RecommendationViewModel.swift` |
| 조건 입력/동 목록/점포 목록 | `apps/eodigaji-ios/Eodigaji/ContentView.swift` |
| 점포별 지도·도보·대중교통 상세 | `apps/eodigaji-ios/Eodigaji/LiveRecommendationDetailView.swift` |
| 지도 핀 선택 | `apps/eodigaji-ios/Eodigaji/OriginPickerView.swift` |
| 로컬 서버 주소 | `apps/eodigaji-ios/Eodigaji/DevelopmentConfiguration.swift` |

## 5. 로컬 실행

### 백엔드

`services/recommendation-api/.env`에 `KAKAO_REST_API_KEY`가 있다. **키 값은 대화·로그·커밋에 절대 출력하지 않는다.**

```bash
cd /Users/woojin/Documents/막시무스/services/recommendation-api
set -a; source .env; set +a
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

헬스체크:

```bash
curl http://127.0.0.1:8000/healthz
```

### iOS

- 프로젝트: `apps/eodigaji-ios/Eodigaji.xcodeproj`
- 앱은 기본적으로 `http://127.0.0.1:8000`을 사용한다.
- 현재 사용한 시뮬레이터: `iPhone 17 Pro`
- Simulator UDID: `959C0327-D8C4-46E2-953C-7C83965C4079`

```bash
xcodebuild test \
  -project apps/eodigaji-ios/Eodigaji.xcodeproj \
  -scheme Eodigaji \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro'
```

백엔드 테스트:

```bash
cd /Users/woojin/Documents/막시무스/services/recommendation-api
python3 -m pytest -q
```

기존 통과 기준:

- 백엔드: 62 passed (FastAPI/httpx 관련 기존 deprecation warning 1개)
- iOS: 40 XCTest passed

## 6. 사업계획서 활동 내역 — 복붙용 문구

원본 사업계획서의 `활동 내역` 3개 행에 아래 문구를 붙여 넣으면 된다.

### 1)

**활동명**

동대문구 룰 기반 추천 알고리즘 설계

**활동 내용**

동대문구 생활권을 대상으로 출발지·방문 목적·이동시간 조건을 반영하는 행정동 추천 규칙과 후보 상권 분류 기준을 설계

### 2)

**활동명**

동대문구 상권·교통 데이터 조사

**활동 내용**

동대문구 행정동·상권·대중교통 접근성 데이터를 조사하고, 목적별 장소 키워드와 후보 선별 기준을 정립

### 3)

**활동명**

목적지 추천 MVP 프론트엔드 제작

**활동 내용**

출발지 검색·상세 위치 지정, 목적·이동시간 선택, 동 추천 및 점포·대중교통 경로 상세 화면을 SwiftUI로 구현

## 7. 사업계획서 파일 관련

- 원본: `output/reports/HUFS_Start-up_Platform_막시무스_사업계획서.docx`
- 이전 작업 중 별도 수정본 `output/reports/HUFS_Start-up_Platform_막시무스_사업계획서_수정.docx`가 생성됐다.
- 원본은 수정하지 않았다. 사용자가 문서 자동수정을 원하지 않으므로 앞으로는 위 복붙용 문구만 제공한다.
- DOCX 메타데이터에는 Microsoft 계정 이메일이 없으며, 마지막 수정자만 `지우진`으로 기록돼 있다.

## 8. 작업 원칙

1. 사용자 소유의 대량 untracked 파일이 존재한다. 관련 없는 파일은 추가·삭제·스테이징하지 않는다.
2. Kakao 키와 `.env`는 커밋하지 않는다.
3. API 호출을 대량으로 반복하면 현재처럼 카카오 한도를 소진할 수 있다. 테스트는 mock/fixture 위주로 하고, 실 API 검증은 최소 1회만 수행한다.
4. 실시간 경로가 없을 때 추정값을 실시간/확정값처럼 표시하지 않는다.
5. 구현 후 백엔드와 iOS 전체 테스트를 모두 실행하고, 시뮬레이터에서 백엔드 연결 상태도 확인한다.
