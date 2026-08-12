# 어디가지 iOS + 추천 API 설계

## 목적

기존 React/Vite 데모를 보존한 채, F0 공개데이터 규칙 기반 MVP를 SwiftUI iOS 앱과 로컬 FastAPI 추천 서비스로 분리한다. 완성 기준은 iOS Simulator에서 조건 입력부터 목적별 추천 결과까지 실행되며, 백엔드가 대중교통 fixture·하드 필터·F0-public-rule 라벨을 일관되게 반환하는 것이다.

## 범위

- iOS: Splash, 게스트 진입, 조건 입력, 추천 결과, 추천 근거, 정보/한계 화면.
- 입력: 출발지, 이동수단(대중교통), 최대 이동시간, 날짜·시간, 목적.
- 백엔드: 추천 요청 검증, 목적별 fixture, 대중교통 하드 필터, 결정적 랭킹, 응답 메타데이터.
- 검증: Swift 단위 테스트, Python API 테스트, iOS Simulator 수동 흐름 점검.

제외: 실제 대중교통 API·API 키, Apple 로그인, 영구 저장소, 제한 데이터 B078/B079, ML, 실시간 운행·영업·개인화.

## 구조

```text
SwiftUI iOS App
  ├─ ConditionForm / Results / Detail / Info
  ├─ RecommendationAPIClient
  └─ App state + accessibility UI
          │ HTTP JSON (localhost)
          ▼
FastAPI recommendation-api
  ├─ request validation
  ├─ TransitProvider protocol (fixture implementation)
  ├─ hard filter
  ├─ F0-public-rule ranking
  └─ response metadata / transparency labels
```

앱은 API URL을 개발용 구성값으로 받는다. 기본값은 Simulator에서 호스트 Mac의 `127.0.0.1`을 사용할 수 없으므로 `localhost`를 쓰지 않고, 실행 시 지정 가능한 base URL을 제공한다. Simulator의 호스트 접속 주소·ATS 예외는 실제 실행 환경에서 최소 범위로 확인한다.

## API 계약

`POST /v1/recommendations`

요청:

```json
{
  "origin": "회기역",
  "transport_mode": "public_transit",
  "max_travel_time_minutes": 30,
  "time_slot": "evening",
  "purpose": "cafe"
}
```

응답은 `result_status`, `eligible_count`, 최대 5개 `recommendations`, 후보별 `journey_time_minutes`, `cost_status`, `reason`, `signal`, `method`, `vintage`, 그리고 전역 `fixture=true`, `ranking_basis="F0-public-rule"`, `limitations`을 반환한다.

대중교통 fixture는 route status·시간·요금을 각각 명시한다. 경로 없음, 시간 누락, 최대 시간 초과 후보는 랭킹 전에 제외한다. 비용 누락은 숫자로 대체하지 않는다.

## 목적별 결과 규칙

식사, 카페, 데이트, 쇼핑, 문화/전시, 산책/휴식은 서로 다른 후보 순서·태그·근거를 가진 fixture 프로필을 사용한다. fixture는 개발 검증용이며 실제 추천값이 아니다. 실제 데이터 공급자는 이후 `TransitProvider` 및 `RecommendationRepository` 경계를 지키는 새 구현으로 교체한다.

## 오류 처리

- 잘못된 입력: API 422와 필드별 한국어 안내.
- 지원하지 않는 이동수단/목적: 안전 오류, 자동 대체 없음.
- 대중교통 데이터·경로·시간 미검증: 결과 미표시 및 오류 상태.
- 적격 후보 0개: 조건 편집을 유도하되 시간/목적을 자동 완화하지 않음.
- 네트워크 실패: 마지막 결과를 새 조건 결과처럼 보이지 않게 하고 재시도 제공.

## 검증 계획

- API: 목적별 결과 차이, hard filter, 경계값(30분 포함/초과 제외), Top 5, fixture/F0 라벨, 입력 오류 테스트.
- iOS: API 디코딩·상태 전이·목적 선택 전달 단위 테스트.
- Simulator: 회기 출발, 대중교통, 30분, 목적을 바꿔 결과 제목·1위·근거가 달라지는지 확인.
- 모든 화면에서 fixture, 공개 데이터 규칙 기반, 실시간 아님·개인화 아님·인과 아님을 표시.

## 리스크와 결정

- 실제 공개 교통 데이터가 아직 검증되지 않았다. 따라서 F0는 fixture API를 명시적으로 표시하고 외부 데이터처럼 표현하지 않는다.
- Simulator 서비스가 현재 응답하지 않았다. 구현 완료 시 서비스 복구 후 대상 기기에서 실행한다.
- iOS 앱은 localhost 백엔드를 직접 가정하지 않는다. 실행 시 확인된 Simulator 호스트 주소를 개발 구성값에 넣는다.
