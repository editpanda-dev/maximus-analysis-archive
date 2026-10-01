# 「어디가지」 F0 MVP 소프트웨어 요구사항 명세서

| 항목 | 내용 |
|---|---|
| 문서 ID | SRS-Eodigaji-F0 |
| 제품 / 팀 | 어디가지 / MAXIMUS |
| 대상 릴리스 | F0 공개 데이터 규칙 기반 모바일 MVP |
| 상태 | 최종 구현·테스트 기준선 |
| 범위 | 390×844 모바일 기준 입력, 후보 하드 필터, F0-public-rule 랭킹, 결과 설명·비교, 빈 상태·오류 상태 |
| 주의 | 이 문서는 구현·운영 데이터·인증·성능 달성의 증명서가 아니다. 검증되지 않은 내용은 명시적으로 분리한다. |

## 1. 목적과 판정 원칙

본 문서는 MAXIMUS가 「어디가지」 F0를 구현하고 테스트할 수 있도록 제품의 관찰된 프로토타입 동작과 최종 PRD 제약을 실행 가능한 요구사항으로 정리한다. 사용자가 출발지, 최대 이동 시간, 날짜·시간, 목적을 입력하면 공개 데이터로 확인 가능한 후보를 먼저 하드 필터하고, 최대 5개를 결정적인 규칙으로 설명 가능하게 보여 주는 범위를 기준선으로 한다.

다음 원칙은 모든 구현·테스트·릴리스 판정에 우선한다.

1. [PRD 설계 결정] 하드 필터는 랭킹보다 먼저 실행한다. 인기 후보라도 경로가 없거나, 이동시간이 누락·미검증이거나, 사용자 최대시간을 초과하면 Top 5에 넣지 않는다.
2. [PRD 설계 결정] F0는 공개·오픈 데이터만 사용한다. 제한 데이터 B078/B079는 F0 런타임, 학습, 추론, 랭킹에서 제외한다.
3. [PRD 설계 결정] 관측 집계는 인과관계나 방문 결과를 증명하지 않는다. 실시간 교통, 영업 상태, 개인화, 방문 보장을 주장하지 않는다.
4. [가정/후속 검증 필요] 실제 공개 데이터의 이름, 스키마, 라이선스, 값, 가용 기간, 갱신주기, 공간 매핑은 아직 검증되지 않았다. DATA 게이트 전에는 구현 사실로 고정하지 않는다.
5. [구현 관찰] 프로토타입의 목적지·수치·점수는 fixture다. 운영 관측값으로 표시하지 않는다.

## 2. 제품 범위

### 2.1 F0 포함

| 영역 | 요구사항 |
|---|---|
| 입력 | origin + max travel time + day/time + purpose를 모두 받는다. |
| 후보 | 검증된 공개 데이터에서 후보를 생성한다. 구체적인 API·공급자·백엔드 구조는 미정이다. |
| 하드 필터 | no route, missing/unverified journey time, over maximum time을 랭킹 전에 제외한다. |
| 랭킹 | same-condition historical inflow, 없으면 global popularity, 없으면 shortest travel time 순이다. |
| 결과 | 최대 Top 5, 이동시간, 비용 또는 명시적 이용 불가, 랭킹 이유, 출처·기준일, 제한사항을 표시한다. |
| 비교 | shortest travel time, global popularity, same-condition historical inflow를 비교하되 검증된 데이터가 없으면 이용 불가로 표시한다. |
| 설명 | F0-public-rule 라벨, signal/method/vintage, 제한사항을 사용자에게 제공한다. |
| 실패 | 입력 오류, unsupported 값, no route, missing time/cost, insufficient eligible, source/vintage unavailable, 조회 실패를 안전하게 안내한다. |
| fixture | 개발·QA 회귀에 한해 static fixture를 사용할 수 있다. 모든 관련 화면에 fixture와 실제 검증 운영값 아님을 표시한다. |

### 2.2 F0 비포함과 명시적 non-goal

- B078/B079 제한 데이터의 접근·다운로드·저장·학습·랭킹 사용.
- 진짜 학습된 ML, 예측 모델, 개인화 모델, 모델 정확도 주장. 학습·검증·테스트와 모델 증거가 없으면 규칙 기반으로만 표시한다.
- 실시간 대중교통, 실시간 영업 중 여부, 개인 선호·방문 이력 기반 개인화.
- 방문 성공, 만족, 매출, 인과 효과, 최적 장소를 보장하는 문구.
- 실제 Apple 로그인, SSO, 계정·토큰·권한 기능. 프로토타입의 Apple UI는 인증 연동 전까지 데모다.
- 인증 서버, 백엔드, DB, 분석 파이프라인, 데이터 공급자, 외부 경로 API의 구체 설계나 존재를 약속하는 것.
- 결과가 없을 때 시스템이 최대시간·날짜·목적을 자동 변경하는 것.

## 3. 문서 provenance와 근거

| ID | 출처 | 용도 |
|---|---|---|
| MAN-01 | archives/source/project-2-2026-08-11.zip | 보존된 원본 프로토타입 |
| MAN-02 | SHA-256 d0d88b1f7d9f20681b1374def05bacbcc38cefa5f0d08767592804bea5372ca0 | 원본 무결성 식별자 |
| MAN-03 | archives/source/project-2-2026-08-11.manifest.md | 아카이브 파일 구성 추적 |
| OBS-01 | 원본 관찰 요약 | Vite 8 + React 19 + TypeScript, dev/build/preview/format scripts |
| OBS-02 | src/App.tsx 관찰 요약 | Splash, Entry, Home, Results, Info, 입력, fixture, 탭·back |
| OBS-03 | src/index.css 관찰 요약 | 390×844 mobile canvas |
| OBS-04 | src/imports/PRD-Where-Do-We-Go.md 및 image.png 관찰 요약 | 아카이브 내 PRD 참조와 자산 |
| PRD-01 | 전달된 최종 PRD 제약 | 입력 계약, 하드 필터, Top 5, fallback 순서 |
| PRD-02 | 전달된 최종 PRD 데이터 경계 | 공개 데이터 F0, B078/B079 F1, 안전·투명성 |

원본 ZIP의 경로와 SHA는 문서 provenance로 기록한다. 이 문서는 원본 아카이브, manifest, PRD, assets, README, source를 수정하지 않는다. src/imports/PRD-Where-Do-We-Go.md가 아카이브에 포함된 것으로 관찰되었고, 최종 PRD 제약은 전달된 authoritative synopsis를 기준으로 한다.

표기 규칙:

- [구현 관찰]: 아카이브 프로토타입에서 보였거나 전달된 현재 상태. 운영 데이터·백엔드·인증의 존재를 뜻하지 않는다.
- [PRD 설계 결정]: 최종 PRD가 F0에 요구하는 제품·릴리스 규칙.
- [가정/후속 검증 필요]: 안전한 구현 해석 또는 외부 확인이 필요한 항목. 검증 전 사실로 고정하지 않는다.

## 4. 용어와 약어

| 용어 | 정의 |
|---|---|
| F0 | 공개 데이터와 결정적 규칙으로 동작하는 MVP |
| F0-public-rule | 공개 데이터 규칙 기반 라벨. ML·학습 모델을 뜻하지 않는다. |
| F1 | B078/B079 접근, 보안, 스키마·감사, 품질 승인을 마친 후 별도 검토할 범위 |
| 후보 | 사용자 조건으로 추천 가능성을 판정하는 장소·지역 레코드 |
| 적격 | 경로, 검증된 이동시간, 최대시간 하드 필터를 모두 통과한 후보 |
| 기준일(vintage) | 값이 관측·생성되었거나 유효한 시점 또는 기간 |
| 동일 조건 | 목적·날짜·시간 등 사용자 조건과 공개 집계가 감사된 방식으로 매핑된 상태 |
| fixture | 개발·테스트용 정적 예시 데이터. 실제 운영값이 아니다. |
| 비교 | 동일 적격 후보 집합을 다른 단일 기준으로 정렬하는 설명용 뷰 |

## 5. 시스템 컨텍스트와 경계

논리 흐름은 다음과 같다.

사용자 → 모바일 UI → 입력 검증 → 공개 데이터 검증 상태 확인 → 후보 생성 → 하드 필터 → F0-public-rule 랭킹 → 결과·설명·비교

이 흐름은 논리 처리 순서이며 특정 서버, DB, API, SDK, 데이터 공급자를 선택했다는 뜻이 아니다.

| 영역 | F0 허용 | F0 금지 또는 F1 조건 |
|---|---|---|
| 데이터 | 출처·스키마·라이선스·값·기준일·공간 매핑이 검증된 공개 데이터 | B078/B079, 출처 없는 값, 검증되지 않은 파일 |
| 계산 | 하드 필터와 결정적 정렬 | ML 추론, 임의 가중치, 누락값을 채운 점수 |
| 사용자 | 인증 없이 실행되는 게스트 입력·결과 | 인증 연동을 가장한 Apple/SSO 상태 |
| 표시 | source, vintage, method, limitations | 출처 없는 숫자, 임의 기준일, 실시간·인과 주장 |
| 실패 | 빈 상태·안전 오류·재시도·조건 편집 | 인기 후보로 자동 채우기, 자동 조건 완화 |

출발지·검색어·좌표는 위치 정보로 최소 수집한다. 영구 저장이나 외부 전송을 전제하지 않는다. 외부 경로 서비스가 추가되면 전송 필드, 보존기간, 처리 근거를 별도 개인정보·보안 검토한다. B078/B079 자격증명·비밀키·인증 토큰을 클라이언트 번들 또는 로그에 넣지 않는다.

## 6. 액터와 역할

| 액터 | 허용 행동 | 경계 |
|---|---|---|
| 미인증 사용자 | 앱 진입, 네 필드 입력, 추천·상세·비교·정보 확인 | 계정·로그인 성공을 전제하지 않는다. |
| 인증 사용자 | 실제 인증이 별도 통합된 뒤에만 정의 가능 | F0 구현·테스트는 인증 서버·자격증명 없이 가능해야 한다. |
| 데이터/관리 운영자 | 공개 데이터 출처, 스키마, 라이선스, 기준일, 매핑, 품질, fixture 검토 | F0 앱에서 B078/B079를 조회하거나 미검증 값을 승인값으로 바꾸지 않는다. |
| QA | 규칙·화면·상태·접근성·fixture·릴리스 게이트 검증 | 테스트 통과를 데이터 품질 승인으로 간주하지 않는다. |

## 7. 사용 사례와 사용자 흐름

| ID | 흐름 | 사전 조건 | 성공/실패 결과 |
|---|---|---|---|
| UC-01 | Splash·Entry | 앱 실행 | Splash 후 인증 없는 F0 입력 경로 |
| UC-02 | 출발지 선택 | Home 진입 | 최근 위치·검색·지도 상세 중 유효한 위치 확정 |
| UC-03 | 조건 입력 | 입력 화면 | 이동수단·최대시간·날짜/시간·목적 선택 |
| UC-04 | 추천 생성 | 네 필드 유효, DATA 상태 확인 | 적격 후보 최대 5개 또는 empty/safe error |
| UC-05 | 상세·근거 | Results 진입 | 시간·비용 상태·이유·출처·기준일·제한 확인 |
| UC-06 | 비교 | 적격 결과 | 같은 적격 집합의 기준별 비교 또는 이용 불가 |
| UC-07 | 정보 | 어느 주요 화면 | F0-public-rule, limitations, provenance 설명 |
| UC-08 | 빈 상태·오류 | 입력·데이터·조회 실패 | 원인·행동 안내, 자동 완화 없음 |
| UC-09 | fixture 회귀 | QA/demo mode | fixture 명시 하에 화면·정렬 검증 |

### 7.1 구체 흐름

1. [구현 관찰] 390×844 iOS-like 캔버스에 pin/path 로고와 “어디가지” Splash가 표시되고 로그인 UI로 이어진다.
2. [PRD 설계 결정] 실제 인증이 없는 F0에서는 Apple 자격증명 없이 Home으로 가는 게스트 경로를 제공한다. Apple 버튼을 남기면 “로그인 연동 전 데모 UI”를 함께 표시하고 성공 로그인으로 처리하지 않는다.
3. [구현 관찰] 출발지는 최근 위치·검색 결과·지도 상세 선택으로 고를 수 있다. 확정되지 않은 위치는 제출하지 않는다.
4. [구현 관찰] 최대시간은 20/30/40/60분, 날짜·시간 슬롯은 morning/lunch/afternoon/evening/night, 목적은 맛집·카페·데이트·쇼핑·문화/전시·산책/휴식이다.
5. [PRD 설계 결정] 이동수단을 선택한다. F0의 기본값은 대중교통이며, 대중교통을 선택하면 검증된 대중교통 경로·이동시간·요금 데이터만 사용한다. 도보·자동차 등 다른 수단은 각 수단의 출처·스키마·경로 검증이 끝난 뒤에만 활성화한다.
6. 추천 실행 직전에 입력을 다시 검증한다. 이동수단을 포함한 필수 입력이 유효하지 않으면 오류를 표시하고 조회하지 않는다.
7. 선택한 이동수단에 대한 source/vintage/mapping/route 상태가 검증되지 않으면 결과를 만들지 않는다.
8. 후보를 선택 수단의 경로, 검증된 이동시간, 최대시간, 조건 매핑 순으로 하드 필터하고 적격 후보만 랭킹한다.
8. 결과는 최대 5개와 실제 eligible_count를 표시한다. 적격 후보가 0이면 empty다. 1~4개면 부족분 없이 실제 개수만 표시한다.
9. 결과 카드의 비용이 없으면 “요금 정보 없음”으로 표시한다. 숫자·통화·0을 만들지 않는다.
10. 결과를 수정된 입력에 재사용하지 않는다. Home에서 조건을 바꾸면 다시 추천해야 한다.

## 8. 기능 요구사항

| ID | 요구사항 | 화면/모듈 | 출처 분류 |
|---|---|---|---|
| FR-001 | Splash는 로고와 “어디가지”를 표시하고 Entry로 전환한다. 인증 성공을 전제하지 않는다. | Splash | [구현 관찰]+[PRD 설계 결정] |
| FR-002 | F0는 인증 자격증명 없이 게스트 입력·추천 흐름을 실행한다. | Entry | [PRD 설계 결정] |
| FR-003 | Apple UI를 보존하면 실제 인증 연동 전 데모임을 표시한다. | Entry | [구현 관찰]+[가정/후속 검증 필요] |
| FR-004 | origin, max travel time, day/time, purpose 네 필드를 필수로 한다. | Home | [PRD 설계 결정] |
| FR-005 | 출발지 선택은 최근 위치·검색·지도 상세 선택을 제공한다. | Location | [구현 관찰] |
| FR-006 | 최대시간은 20/30/40/60분, 목적은 6개, 시간 슬롯은 5개를 제공한다. | Home | [구현 관찰] |
| FR-007 | 과거·미지원 날짜/시간은 재선택 오류를 표시하고 자동 변경하지 않는다. | Date/Time | [PRD 설계 결정] |
| FR-008 | 필수 입력이 유효하지 않으면 추천을 실행하지 않는다. | Home | [PRD 설계 결정] |
| FR-009 | 추천 전 source, vintage, schema, license, mapping 상태를 확인한다. | Data gate | [PRD 설계 결정] |
| FR-010 | no route, missing/unverified journey time, over max time을 랭킹 전에 제외한다. | Hard filter | [PRD 설계 결정] |
| FR-011 | 최대시간과 동일한 이동시간은 적격으로 처리한다. | Hard filter | [가정/후속 검증 필요] |
| FR-012 | 적격 후보만 same-condition → global popularity → shortest travel time 순으로 정렬한다. | Ranking | [PRD 설계 결정] |
| FR-013 | 결과는 최대 5개이며 실제 eligible_count를 표시한다. | Results | [구현 관찰]+[PRD 설계 결정] |
| FR-014 | 카드에 이동시간, 비용 또는 이용 불가, 이유, source, vintage, limitation을 표시한다. | Results | [PRD 설계 결정] |
| FR-015 | 추천 근거 확장 영역에 signal, method, vintage를 표시한다. | Detail | [구현 관찰]+[PRD 설계 결정] |
| FR-016 | 비교는 같은 적격 후보 집합의 shortest travel time, global popularity, same-condition 기준만 사용한다. | Comparison | [PRD 설계 결정] |
| FR-017 | eligible=0이면 자동 조건 완화 없이 empty와 조건 편집을 제공한다. | Empty | [PRD 설계 결정] |
| FR-018 | 사용자-visible 라벨은 F0-public-rule이며 ML·학습·예측으로 부르지 않는다. | Results/Info | [PRD 설계 결정] |
| FR-019 | 실시간 교통·영업 상태·개인화·인과성·방문 보장 부재와 기준일·제한사항을 표시한다. | Results/Info | [PRD 설계 결정] |
| FR-020 | 입력 수정 후 이전 결과를 새 조건의 결과로 재사용하지 않는다. | State | [가정/후속 검증 필요] |
| FR-021 | fixture 결과는 전역적으로 fixture와 실제 운영 검증값 아님을 표시한다. | QA/demo | [구현 관찰]+[PRD 설계 결정] |
| FR-022 | source/vintage/라이선스/스키마/공간 매핑 미검증 시 운영 결과를 차단한다. | Data gate | [PRD 설계 결정] |
| FR-023 | 알 수 없는 값을 빈 문자열·0·임의 label로 대체하지 않는다. | Data/result | [PRD 설계 결정] |
| FR-024 | 이동수단을 필수 입력으로 제공하며 F0 기본값은 대중교통이다. | Home | [PRD 설계 결정] |
| FR-025 | 대중교통 선택 시 대중교통 경로가 available_verified이고 해당 수단의 이동시간이 verified인 후보만 하드 필터를 통과시킨다. | Routing/Hard filter | [PRD 설계 결정] |
| FR-026 | 선택한 이동수단별로 이동시간·요금·경로 상태·기준일·출처를 결과와 상세에 표시한다. | Results/Detail | [PRD 설계 결정] |
| FR-027 | 선택 수단의 교통 데이터가 미검증·미지원·오프라인이면 다른 수단의 값으로 자동 대체하지 않고 안전 오류를 표시한다. | Routing/Error | [PRD 설계 결정] |

## 9. 입력 계약과 검증

| ID | 필드 | 허용값 | 필수성/실패 |
|---|---|---|---|
| DATA-IN-01 | origin | 사용자가 확인한 위치 참조·표시명. 실제 좌표/외부 ID는 미확정 | 필수, ERR-ORIGIN |
| DATA-IN-02 | max_travel_time_minutes | 20, 30, 40, 60 정수 | 필수, ERR-TIME-LIMIT |
| DATA-IN-03 | day | 한국어 달력 날짜 | 필수, ERR-DAY-TIME |
| DATA-IN-04 | time_slot | morning/lunch/afternoon/evening/night | 필수, ERR-DAY-TIME |
| DATA-IN-05 | purpose | 맛집/카페/데이트/쇼핑/문화·전시/산책·휴식 | 필수, ERR-PURPOSE |
| DATA-IN-06 | transport_mode | public_transit(기본), 기타 수단은 DATA-VAL-11 통과 후 활성화 | 필수, ERR-TRANSPORT-MODE |

실제 저장키, API 필드명, 좌표 정밀도, 날짜 포맷, 시간대는 데이터·플랫폼 검증 전 미확정이다. 과거 날짜와 당일 이미 지난 슬롯은 기본적으로 거부한다. 시스템 시각·시간대·데이터 커버리지가 불명확하면 임의의 현재 시각·지원 범위를 사용하지 않고 오류를 표시한다. 사용자가 고른 값을 다른 날짜·시간·목적·최대시간으로 자동 변경하지 않는다.

## 10. 하드 필터와 F0-public-rule 랭킹

### 10.1 필터 규칙

적격 후보는 다음을 모두 만족한다.

1. 선택한 transport_mode의 route_status가 available_verified다. public_transit이면 대중교통 경로여야 한다.
2. 선택한 transport_mode의 journey_time_minutes가 존재하고 verified다.
3. journey_time_minutes가 max_travel_time_minutes 이하이다.
4. 후보와 목적·날짜·시간의 조건 매핑이 verified다.

비용 누락은 PRD 하드 필터의 이동시간·경로를 대체하지 않는다. 위 조건을 통과하고 비용만 없으면 결과에 남길 수 있으나 비용을 숫자로 표시하거나 랭킹에 쓰지 않고 “요금 정보 없음”으로 표시한다. 비용도 필수 적격 조건으로 만들지는 [가정/후속 검증 필요]이며 별도 승인 없이는 변경하지 않는다.

### 10.2 랭킹 선택과 동률

same-condition은 적격 집합 전체의 값·출처·기준일·조건 매핑·품질 검증이 완료된 경우에만 사용한다. 일부 후보의 값만 있으면 누락을 0으로 채우거나 다른 기준과 임의로 섞지 않고 다음 기준으로 fallback한다.

1. 검증된 same-condition historical inflow가 있으면 해당 지표 내림차순.
2. 없으면 검증된 global popularity 내림차순.
3. 둘 다 없으면 shortest travel time 오름차순.

동률은 항상 journey_time_minutes 오름차순, 그 다음 정규화한 candidate_id 사전식 오름차순이다. candidate_id가 없거나 충돌하면 운영 결과를 게시하지 않고 DATA-IDENTITY 오류를 낸다. 가중치, 랜덤, 이름 순서, 인기순을 임의의 마지막 tie-breaker로 쓰지 않는다.

### 10.3 의사코드

    function recommend(input, candidates, source):
        validate input
        require source.status == verified
        require source.source_name and source.vintage and source.mapping_status == verified

        eligible = []
        for candidate in candidates:
            if candidate.route_status[input.transport_mode] != available_verified:
                exclude(candidate, NO_ROUTE_OR_UNVERIFIED_ROUTE)
            else if candidate.journey_time_status[input.transport_mode] != verified
                 or candidate.journey_time_minutes[input.transport_mode] is missing:
                exclude(candidate, MISSING_OR_UNVERIFIED_JOURNEY_TIME)
            else if candidate.journey_time_minutes[input.transport_mode] > input.max_travel_time_minutes:
                exclude(candidate, OVER_MAX_TRAVEL_TIME)
            else if candidate.condition_mapping_status != verified:
                exclude(candidate, UNSUPPORTED_OR_UNVERIFIED_CONDITION)
            else:
                eligible.append(candidate)

        if eligible is empty:
            return EMPTY_WITHOUT_AUTOMATIC_RELAXATION

        if verified_complete_same_condition_metric(eligible):
            basis = same-condition-historical-inflow
            sort by metric descending, journey time ascending, candidate_id ascending
        else if verified_complete_global_popularity(eligible):
            basis = global-popularity
            sort by metric descending, journey time ascending, candidate_id ascending
        else:
            basis = shortest-travel-time
            sort by journey time ascending, candidate_id ascending

        return first five eligible candidates with basis and source

verified_complete의 실제 품질 조건은 DATA 게이트에서 확정한다. 이 의사코드는 API, 공급자, 실제 값 또는 ML 모델을 발명하지 않는다.

## 11. 데이터 모델과 검증 게이트

### 11.1 논리 데이터 모델

| 객체 | 필드 | 규칙 |
|---|---|---|
| UserInput | query_id, origin_ref, origin_label, transport_mode, max_travel_time_minutes, day, time_slot, purpose | 이동수단을 포함한 필수 입력, query_id별 스냅샷 |
| Candidate | candidate_id, name, district, route_status_by_mode, journey_time_by_mode/status/vintage, cost_by_mode/status, condition_mapping_status, same_condition_inflow, global_popularity, tags, fixture, source_ref | candidate_id·선택 수단 경로·검증 이동시간은 운영 필수; metric/cost는 미검증이면 비어 있음 |
| Recommendation | query_id, result_status, eligible_count, top_candidates, ranking_basis/version, source_metadata, limitations | top_candidates 0~5이며 모두 eligible |
| RankingExplanation | rank, reason_label, signal_name/value, method, vintage, comparator_refs, limitation | 선택된 기준의 근거만 표시; 값 누락 시 생략 |
| SourceMetadata | source_name, schema/version, licence_status, availability, vintage, coverage, mapping_status, quality_status, fixture | 필수 항목 검증 전 운영 결과 표시 금지 |

실제 필드명, 타입, null 정책, 단위, 좌표계, 집계기간, 외부 ID는 검증 전 미확정이다. 프로토타입의 성수동, 연남동, 을지로, 건대입구, 망원동과 표시 숫자는 fixture로만 취급한다.

[구현 관찰] 프로토타입 결과 fixture에서 관찰된 표시 필드는 rank, name, district, time, cost, score, score label, tags, reason과 signal/method/vintage 상세다. [PRD 설계 결정] F0 운영에서 score와 score label은 계산 규칙·값·출처·기준일이 검증된 경우에만 표시하고, 그렇지 않으면 숨긴다. fixture의 점수·태그·이유는 실제 운영 지표로 재사용하지 않는다.

### 11.2 DATA 검증 게이트

| ID | 게이트 | 통과 증거 | 미통과 시 |
|---|---|---|---|
| DATA-VAL-01 | 공개 출처명·소유자·접근 경로 | 출처 문서와 재현 가능한 식별자 | 운영 결과 차단 |
| DATA-VAL-02 | 스키마·단위·필수값·결측 규칙 | 스키마 검토와 샘플 검증 | 랭킹·표시 차단 |
| DATA-VAL-03 | 라이선스·사용범위 | 승인된 사용조건 기록 | no-go |
| DATA-VAL-04 | 값·갱신주기·기준일 | 실제 값 검증과 vintage 기록 | source/vintage 오류 |
| DATA-VAL-05 | origin-to-candidate 공간/경로 매핑 | 좌표계·매핑·경로 감사 | 후보 생성 차단 |
| DATA-VAL-06 | 목적·날짜·시간 조건 매핑 | 정의·커버리지 기록 | 해당 metric fallback 또는 오류 |
| DATA-VAL-07 | 이동시간·경로 품질 | missing/no-route/stale 판정 | 하드 필터·안전 오류 |
| DATA-VAL-08 | fixture 분리 | fixture flag와 화면 검증 | 오인 가능 시 no-go |
| DATA-VAL-09 | B078/B079 독립성 | 자격증명·접근 호출 없음 | F0 no-go |
| DATA-VAL-10 | ML 미표기 | 학습·검증·테스트·모델 증거 없음 확인 | 규칙 라벨로 수정 전 no-go |
| DATA-VAL-11 | 교통수단 데이터 | 수단별 출처·스키마·라이선스·경로·시간·요금·기준일·공간 매핑 검증 | 해당 수단 비활성화·운영 결과 차단 |
| DATA-VAL-12 | 대중교통 경로 | 출발지→후보 대중교통 경로와 환승·도보 포함 범위, 시간·요금 산출 기준 검증 | public_transit 결과 차단 |

실제 public source name, schema, availability, licence, values는 이 SRS에 고정하지 않는다. 게이트를 통과하지 않은 임의의 시간·비용·인기도·유입 값을 운영 기본값으로 넣지 않는다.

## 12. 상태 모델과 내비게이션

| 상태 ID | 의미 | 전이 |
|---|---|---|
| STATE-SPLASH | 로고·제품명 | ENTRY |
| STATE-ENTRY | Entry/데모 로그인 UI | HOME, INFO |
| STATE-HOME-INCOMPLETE | 입력 일부 누락 | LOCATION, DATE_TIME, PURPOSE, HOME-VALID |
| STATE-HOME-VALID | 네 필드 유효 | LOADING |
| STATE-LOCATION | 출발지 선택 | HOME-INCOMPLETE/HOME-VALID |
| STATE-DATE_TIME | 날짜·시간 선택 | HOME-INCOMPLETE/HOME-VALID |
| STATE-PURPOSE | 목적 선택 | HOME-INCOMPLETE/HOME-VALID |
| STATE-LOADING | 추천 처리 | RESULTS, EMPTY, ERROR |
| STATE-RESULTS | 성공 결과 | DETAIL, COMPARISON, HOME, INFO |
| STATE-DETAIL | 근거·상세 확장 | RESULTS |
| STATE-COMPARISON | 비교 | RESULTS, ERROR |
| STATE-EMPTY | eligible 0 또는 부족 안내 | HOME |
| STATE-ERROR | 안전 오류 | HOME, RETRY, INFO |
| STATE-INFO | 방법·제한 | 이전 화면 |

불변식:

- LOADING은 유효한 입력 스냅샷에만 진입한다.
- RESULTS 카드 수는 5 이하이고 모두 eligible이다.
- HOME 입력 변경은 이전 결과를 무효화하거나 “이전 조건 결과”로 구분한다. 새 조건의 결과처럼 표시하지 않는다.
- EMPTY는 조건을 자동 변경하지 않는다.
- 중복 추천은 하나의 query_id로 직렬화하거나 취소하며, 서로 다른 조건의 응답을 섞지 않는다.
- [구현 관찰] 하단 탭은 home/results/info, 결과에는 back navigation이 있다. Results 성공 결과가 없으면 Results 탭은 Home 또는 안내 상태를 보인다.

## 13. UI/UX와 접근성

| ID | 요구사항 |
|---|---|
| UI-001 | 390×844를 기본 회귀 캔버스로 사용한다. |
| UI-002 | 좁고 넓은 화면에서 잘림·겹침 없이 세로 스크롤·유연한 폭을 사용한다. 지원 폭은 QA에서 확정한다. |
| UI-003 | Splash, Entry, Home, Location, Date/Time, Purpose, Results, Detail, Comparison, Info, Empty, Error를 구분한다. |
| UI-004 | Results 상단에 조건 요약, eligible_count, ranking basis를 확인 가능하게 한다. |
| UI-005 | source, vintage, fixture, limitation, F0-public-rule을 장식·색상·숨은 tooltip에만 의존하지 않는다. |
| UI-006 | 비용 미확인은 숫자·통화·0이 아니라 “요금 정보 없음”이다. |
| UI-007 | 로딩·empty·error는 stale 결과와 섞이지 않는다. |

- 한국어 텍스트는 잘리지 않고, 글자 확대·스크린리더에서도 핵심 입력·결과·오류가 읽힌다.
- 터치 대상은 겹치지 않고 충분한 간격과 크기를 가진다. 플랫폼별 픽셀 수치는 최신 접근성 정책과 실제 기기 QA에서 정한다.
- 키보드·외부 키보드·스크린리더의 포커스 순서는 시각적 입력 순서와 같고 현재 포커스가 보인다.
- 선택됨, 적격, 제외, 오류, fixture는 색상 외 텍스트·아이콘·상태 속성으로도 전달한다.
- 세그먼트, 달력, 시간 슬롯, 목적 선택, 카드 확장은 역할·선택 상태·포커스를 보조기술에 전달한다.
- 오류 시 원인과 해당 입력으로 이동할 방법을 제공한다.
- reduced motion을 존중하며 애니메이션이 없어도 기능과 상태가 이해된다.
- 지도 선택을 보조기술이 사용할 수 없으면 검색·텍스트 선택 경로를 제공한다.
- 명도 대비, 최소 글자 크기, 플랫폼별 터치 수치는 임의로 고정하지 않고 QA 증거로 남긴다.

## 14. 로딩·오류·빈 상태

| ID | 조건 | 권장 한국어 문구 | 처리 |
|---|---|---|---|
| ERR-INPUT-MISSING | 필수값 누락 | “출발지, 이동수단, 시간, 날짜·시간, 목적을 모두 선택해 주세요.” | 누락 필드 안내, 실행 차단 |
| ERR-TRANSPORT-MODE | 이동수단 미선택·미지원 | “이동수단을 선택해 주세요. 현재 지원되는 수단만 사용할 수 있어요.” | 수단 재선택, 실행 차단 |
| ERR-TRANSPORT-DATA | 선택 수단의 교통 데이터·경로·시간·요금 미검증 | “선택한 이동수단의 교통 정보를 확인할 수 없어 추천을 표시할 수 없어요.” | 자동 수단 대체 없이 안전 오류 |
| ERR-ORIGIN | 출발지 미확정·지원 불가 | “출발지를 확인할 수 없어요. 다른 위치를 선택해 주세요.” | 위치 재선택 |
| ERR-PURPOSE | 목적 누락·지원 불가 | “이 목적은 현재 추천할 수 없어요. 다른 목적을 선택해 주세요.” | 목적 재선택 |
| ERR-TIME-LIMIT | enum 밖 | “이동 시간을 다시 선택해 주세요.” | 20/30/40/60 중 재선택 |
| ERR-DAY-TIME | 과거·미지원·시간대 불명 | “선택한 날짜·시간은 사용할 수 없어요. 이용 가능한 날짜와 시간을 선택해 주세요.” | 자동 변경 없이 재선택 |
| ERR-NO-ROUTE | 선택 수단의 경로 없음 | “선택한 이동수단과 조건에서 이동 경로를 확인할 수 있는 후보가 없어요.” | empty/조건 편집 |
| ERR-JOURNEY-TIME | 시간 누락·미검증 | “이동 시간 정보를 확인할 수 없어 해당 후보를 제외했어요.” | 후보 제외, 시간 발명 금지 |
| ERR-COST-MISSING | 적격 후보 비용 누락 | “요금 정보 없음” | 숫자·통화·0 금지 |
| ERR-OVER-LIMIT | 최대시간 초과 | “선택한 시간 안에 도달할 수 없어 추천에서 제외했어요.” | 후보 제외·복귀 금지 |
| ERR-DATA-SOURCE | 출처·스키마·라이선스 미확인 | “추천 데이터의 출처와 기준일을 확인할 수 없어 결과를 표시할 수 없어요.” | 안전 오류, 가짜 결과 금지 |
| ERR-VINTAGE | 기준일·커버리지 불가 | “데이터 기준일을 확인할 수 없어 추천을 표시할 수 없어요.” | 재시도/검증 후 재실행 |
| ERR-MAPPING | 조건·공간 매핑 불가 | “선택한 조건과 장소 데이터를 연결할 수 없어요. 조건을 다시 선택해 주세요.” | 조건 재선택 |
| ERR-IDENTITY | candidate_id 누락·충돌 | “추천 데이터를 확인하는 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.” | 이름순 대체 금지 |
| ERR-NO-ELIGIBLE | eligible 0 | “선택한 조건에 맞는 후보가 없어요. 조건을 직접 바꿔 다시 찾아보세요.” | 자동 완화 없음 |
| ERR-INSUFFICIENT | eligible 1~4 | “조건에 맞는 후보가 N개뿐이에요.” | N개만 표시 |
| ERR-UNAVAILABLE | 조회·로컬 데이터·네트워크 불가 | “추천 데이터를 불러오지 못했어요. 연결 상태를 확인하고 다시 시도해 주세요.” | 같은 조건 재시도 |
| ERR-OFFLINE | 운영 데이터 오프라인 접근 불가 | “현재 오프라인이라 검증된 추천을 표시할 수 없어요.” | 검증된 fixture가 아니면 표시 금지 |
| ERR-AUTH-DEMO | Apple UI에 실제 연동 없음 | “로그인 연동 전 데모 화면이에요. 인증 없이 추천을 이용해 보세요.” | 게스트 경로 제공 |

N은 실제 eligible_count로 치환한다. 추천·근거·재시도 로딩 문구는 각각 “조건에 맞는 후보를 확인하고 있어요.”, “추천 근거를 불러오는 중이에요.”, “같은 조건으로 다시 확인하고 있어요.”로 하고, 무한 spinner·성공처럼 보이는 fallback을 금지한다.

## 15. 비기능 요구사항

### 15.1 성능·가용성

다음은 실제 결과가 아닌 [가정/후속 검증 필요] 제안 검증 목표다. 측정 환경·데이터 크기·네트워크·기기 합의 전에는 성능이나 uptime을 주장하지 않는다.

| ID | 목표/요구 | 검증 |
|---|---|---|
| NFR-PERF-001 | 입력·탭 전환은 대상 기기에서 즉시 이해 가능한 피드백을 제공한다. 정량 기준은 플랫폼 QA가 합의한다. | 실제 390×844 기기 |
| NFR-PERF-002 | 추천 시작부터 Results/Empty/Error까지의 p50/p95 목표와 cold/warm 조건을 릴리스 전에 정한다. | 연결·데이터 크기별 측정 |
| NFR-PERF-003 | 조회 지연·실패는 무한 로딩 없이 안전 상태로 종료한다. | timeout·부분 응답·오프라인 |
| NFR-AVAIL-001 | 실제 운영 형태가 로컬인지 네트워크인지 미정이므로 SLA·offline cache를 약속하지 않는다. | 문서·릴리스 검토 |
| NFR-AVAIL-002 | 검증된 데이터에 접근할 수 없으면 ERR-OFFLINE 또는 ERR-UNAVAILABLE을 표시한다. | 네트워크 차단 |

### 15.2 보안·개인정보

| ID | 요구 |
|---|---|
| NFR-SEC-001 | F0 실행은 B078/B079와 자격증명에 의존하지 않는다. |
| NFR-SEC-002 | 출발지·검색어·좌표는 최소 수집·최소 전송하며 저장·보존기간은 별도 승인한다. |
| NFR-SEC-003 | 위치·토큰·비밀키·원본 외부응답을 기본 로그에 남기지 않는다. |
| NFR-SEC-004 | 클라이언트 번들에 비밀키·B078/B079 자격증명·실제 인증 비밀을 넣지 않는다. |
| NFR-SEC-005 | 외부 데이터/경로 서비스 추가 시 전송 필드·보존·실패 처리를 보안·개인정보 검토한다. |
| NFR-SEC-006 | F0에 실제 권한 분리·계정 세션이 없음을 UI·문서에서 명확히 한다. |

### 15.3 관측성·감사·정확성

분석 파이프라인이 이미 존재한다는 뜻이 아닌 논리 이벤트 요구사항이다. 실제 수집은 개인정보 검토 후 선택한다.

| 이벤트/감사 필드 | 최소 내용 |
|---|---|
| recommendation_started | query_id, 입력 검증 상태 |
| candidate_filter_summary | query_id, 제외 사유별 수, eligible_count |
| ranking_completed | query_id, ranking_basis, 규칙 버전, source ref, vintage, fixture |
| safe_error_shown | error ID, query_id, source status |
| 결과 재현 기록 | 입력 스냅샷, 적격 집합, 제외 사유, tie-breaker, 결과 순서 |

정밀 위치·raw 검색어·인증 정보·원본 응답은 기본 기록하지 않는다. 숫자에는 source/vintage를 연결하고, “실시간”, “AI가 예측”, “방문 확률”, “효과가 입증됨” 같은 표현은 F0에서 사용하지 않는다.

### 15.4 유지보수·테스트 가능성

- 하드 필터, basis 선택, tie-breaker, Top 5 제한은 UI와 분리된 결정적 로직으로 테스트 가능해야 한다.
- 동일 입력·동일 검증 데이터는 동일한 순서·설명을 반환한다.
- 데이터 공급자가 바뀌어도 source/vintage/fixture 상태를 갱신할 수 있어야 한다.
- B078/B079 호출 여부를 환경 격리와 코드 검토로 확인한다.
- 자동 테스트가 없는 영역은 수동 QA/릴리스 게이트에 남기고 테스트 완료로 표시하지 않는다.

## 16. 수용 기준과 테스트 매트릭스

### 16.1 수용 기준

| ID | 수용 기준 |
|---|---|
| ACC-001 | 네 필드가 모두 유효하지 않으면 추천이 실행되지 않고 오류 필드가 안내된다. |
| ACC-002 | 출발지 검색·최근·지도 상세 흐름에서 미확정 위치는 제출되지 않는다. |
| ACC-003 | 20/30/40/60, 5개 시간 슬롯, 6개 목적이 선택·표시된다. |
| ACC-004 | no route 후보는 인기여도 제외된다. |
| ACC-005 | 이동시간 누락·미검증 후보는 제외된다. |
| ACC-006 | 초과 후보는 제외되고 최대값 동일 후보는 포함된다. |
| ACC-007 | 제외 후보는 Top 5·eligible_count·비교에 복귀하지 않는다. |
| ACC-008 | 랭킹 fallback이 same-condition → global popularity → shortest travel time 순이다. |
| ACC-009 | 임의 가중치·누락값 0 대체·랜덤 정렬·ML 표기가 없다. |
| ACC-010 | 동률은 이동시간, candidate_id 순으로 반복 실행해도 동일하다. |
| ACC-011 | 결과는 최대 5개이고 0·1~4개를 실제 수로 처리한다. |
| ACC-012 | 카드에 이동시간, 비용 또는 이용 불가, 이유, source, vintage, limitation이 있다. |
| ACC-013 | 비용 누락은 “요금 정보 없음”이며 가짜 숫자가 없다. |
| ACC-014 | source/vintage/license/schema/mapping 미검증 시 운영 결과를 표시하지 않는다. |
| ACC-015 | F0-public-rule과 제한사항이 보이고 ML·인과·방문 보장 오해가 없다. |
| ACC-016 | 부분 metric을 0으로 채우지 않고 전체 basis를 보수적으로 fallback한다. |
| ACC-017 | comparator가 동일 적격 집합만 사용한다. |
| ACC-018 | empty에서 자동 조건 완화가 없고 사용자 편집만 제공한다. |
| ACC-019 | Splash→Entry→Home→Results/Empty/Error, 탭, back navigation이 390×844에서 회귀하지 않는다. |
| ACC-020 | fixture 모든 화면에 fixture와 실제 운영값 아님이 표시된다. |
| ACC-021 | B078/B079·자격증명 없이 F0 빌드·테스트·실행이 가능하다. |
| ACC-022 | 색상 없이 상태를 이해하고 포커스·스크린리더·reduced motion이 동작한다. |
| ACC-023 | 성능·가용성 결과가 없으면 그 결과를 주장하지 않고 제안 목표만 기록한다. |
| ACC-024 | public_transit 선택 시 대중교통 경로·시간·요금의 출처·기준일·검증 상태가 표시되고, 다른 수단 값이 섞이지 않는다. |
| ACC-025 | 대중교통 데이터가 없거나 미검증이면 대중교통 결과를 추정·대체하지 않고 ERR-TRANSPORT-DATA를 표시한다. |

### 16.2 테스트 매트릭스

전달된 자료에서 자동 테스트 파일이나 실행 결과는 확인되지 않았다. 따라서 아래는 제안 테스트이며, 관찰된 UI는 자동 통과 증거가 아니다.

| Test ID | 유형 | 검증 대상 | 조건 | 기대 결과 |
|---|---|---|---|---|
| TEST-001 | 단위 | ACC-001 | 각 필드 누락 | 실행 차단·ERR-INPUT-MISSING |
| TEST-002 | UI 회귀 | ACC-003 | enum·슬롯·목적 전체 | 선택 상태와 표시 일치 |
| TEST-003 | 단위 | ACC-004 | no route + high popularity | 제외 |
| TEST-004 | 단위 | ACC-005 | missing/unverified time | 제외 |
| TEST-005 | 경계값 | ACC-006 | 최대값 동일·초과 | 동일 포함·초과 제외 |
| TEST-006 | 단위 | ACC-007 | 제외 10, 적격 6 | Top 5는 적격뿐, count=6 |
| TEST-007 | 단위 | ACC-008 | 세 metric 검증 | same-condition |
| TEST-008 | 단위 | ACC-008 | same 없음, global 있음 | global |
| TEST-009 | 단위 | ACC-008 | 두 metric 없음 | shortest travel time |
| TEST-010 | 단위 | ACC-016 | 부분 metric | 0 채움·혼합 없음, 보수적 fallback |
| TEST-011 | 단위 | ACC-010 | metric·시간 동률 반복 | candidate_id 순서 고정 |
| TEST-012 | 결과 | ACC-011 | eligible 0/1/4/5/6 | empty/실제 수/최대 5 |
| TEST-013 | 결과 | ACC-012~013 | cost missing | 요금 정보 없음, 숫자 없음 |
| TEST-014 | 데이터 게이트 | ACC-014 | source/vintage/license/schema/mapping 누락 | safe error·운영 결과 차단 |
| TEST-015 | 콘텐츠 | ACC-015 | 화면 문구 검색·검토 | F0-public-rule, ML 오표기 없음 |
| TEST-016 | 비교 | ACC-017 | excluded 후보 포함 | comparator에 재등장 안 함 |
| TEST-017 | 수동 | ACC-018 | eligible 0 | 시간·목적 자동 완화 없음 |
| TEST-018 | 회귀 | ACC-019 | Splash/Home/Results/Info/back/tabs | 상태·내비게이션 일치 |
| TEST-019 | fixture | ACC-020 | 5개 static destination | fixture 표기와 실제 아님 문구 |
| TEST-020 | 격리 | ACC-021 | B078/B079 env/credential 없음 | F0 완료 |
| TEST-021 | 통합 | ACC-022 | 색상 제거·스크린리더·확대·reduced motion | 상태·포커스·가독성 유지 |
| TEST-022 | 실패 | ACC-023 | offline/timeout/source unavailable | 무한 로딩·stale/fake fallback 없음 |
| TEST-023 | 통합 | ACC-008 | fallback 순서와 reason | 기준과 설명 일치 |
| TEST-024 | 수동 | ACC-023 | 성능 evidence 없음 | 성능·SLA 결과 주장 없음 |
| TEST-025 | 통합 | ACC-024 | public_transit, 환승·도보 포함 경로 fixture | 대중교통 기준 시간·요금·출처·빈티지 일치 |
| TEST-026 | 실패 | ACC-025 | 대중교통 source/route/time/cost 검증 누락 | 결과 차단·자동 수단 대체 없음 |

### 16.3 커버리지 갭

| 영역 | 현재 증거 | 갭 |
|---|---|---|
| 자동 테스트 | 전달 패킷에 테스트 실행 증거 없음 | TEST-001~024 작성·실행 필요 |
| 화면 | Splash, 입력, 결과, Info, tabs/back 관찰 | 자동 UI 회귀·접근성 필요 |
| 데이터 | source/schema/licence/value/availability 미검증 | DATA-VAL-01~10 blocker |
| B078/B079 독립성 | PRD 경계만 있음 | 환경 격리·코드 검색 필요 |
| 성능·가용성 | 결과 없음 | 제안 목표·측정 환경 필요 |

## 17. 추적성(Traceability)

### 17.1 요구사항 출처

| ID | 유형 | 요약 |
|---|---|---|
| OBS-01 | 구현 관찰 | Vite 8, React 19, TypeScript와 scripts |
| OBS-02 | 구현 관찰 | App.tsx 화면·입력·결과·내비게이션 |
| OBS-03 | 구현 관찰 | 390×844 캔버스 |
| OBS-04 | 구현 관찰 | inline SVG/logo, image.png, fixture |
| OBS-05 | 구현 관찰 | 시간 20/30/40/60, 목적 6종, 슬롯 5종 |
| OBS-06 | 구현 관찰 | static destination 5개, score/reason/signal/method/vintage |
| PRD-01 | PRD 설계 결정 | 네 필수 입력 계약 |
| PRD-02 | PRD 설계 결정 | 하드 필터 선행, Top 5, 제외 복귀 금지 |
| PRD-03 | PRD 설계 결정 | ranking fallback과 comparator |
| PRD-04 | PRD 설계 결정 | 공개 데이터 F0, B078/B079 F1, ML 금지 |
| PRD-05 | PRD 설계 결정 | empty/error, 투명성, 자동 완화 금지 |
| PRD-06 | PRD 설계 결정 | 실시간·개인화·인과·방문 보장 부재 |
| MAN-01 | provenance | ZIP path/SHA |
| MAN-02 | provenance | manifest path |
| VAL-01 | 가정/후속 검증 필요 | 실제 공개 데이터와 값·라이선스·매핑 미검증 |

### 17.2 추적성 표

| 요구사항 | 근거 | 검증 |
|---|---|---|
| FR-001~003, UI-001 | OBS-02~03, PRD-05 | TEST-018 |
| FR-004~008, DATA-IN-01~05 | OBS-02, OBS-05, PRD-01 | TEST-001~002 |
| FR-010~011 | PRD-02 | TEST-003~006 |
| FR-009, FR-022~023, DATA-VAL-* | PRD-04, VAL-01, MAN-01~02 | TEST-014, TEST-020, TEST-022 |
| FR-012, ACC-008~010 | PRD-03~04 | TEST-007~011, TEST-023 |
| FR-013~015, UI-004~007 | OBS-02, OBS-06, PRD-05~06 | TEST-012~015, TEST-019 |
| FR-016, ACC-017 | OBS-02, PRD-03 | TEST-016 |
| FR-017, ERR-* | PRD-05~06 | TEST-017, TEST-022 |
| FR-018~019 | PRD-04~06 | TEST-015 |
| FR-020, STATE-* | OBS-02, PRD-05 | TEST-018 |
| NFR-SEC, NFR-PERF, 관측성 | PRD-04~06, VAL-01 | TEST-020~024, 별도 검토 |

### 17.3 아카이브 파일 연결

| 경로 | 연결 |
|---|---|
| archives/source/project-2-2026-08-11.zip | MAN-01~02, 전체 provenance |
| archives/source/project-2-2026-08-11.manifest.md | MAN-03, 파일 구성 추적 |
| src/App.tsx | FR, UI, STATE, TEST-018~019 |
| src/index.css | UI-001~002, TEST-018 |
| src/imports/PRD-Where-Do-We-Go.md | PRD-01~06 참조 |
| src/imports/image.png와 inline SVG | UC-01, UI-001 |

## 18. 의존성·위험·가정·열린 질문

### 18.1 의존성과 위험

| ID | 내용 | 대응/판정 |
|---|---|---|
| DEP-001 | 공개 데이터 출처·라이선스 필요 | DATA-VAL-01~04 전 운영 표시 금지 |
| DEP-002 | origin-to-candidate 경로·공간 매핑 필요 | DATA-VAL-05 전 후보 생성 금지 |
| DEP-003 | 목적·날짜·시간 커버리지 필요 | DATA-VAL-06 전 metric fallback 또는 오류 |
| DEP-004 | fixture 분리 필요 | fixture flag·전역 표시·운영 빌드 점검 |
| RISK-001 | 정적 장소·수치가 실제 인기·시간으로 오인 | fixture 표시 또는 검증 데이터로 교체 |
| RISK-002 | stale route/time | vintage·검증 상태, 하드 필터·안전 오류 |
| RISK-003 | 부분 metric의 0 대체 | 전체 집합 검증 실패 시 다음 basis |
| RISK-004 | 인증 UI 오인 | 게스트 경로와 데모 문구 |
| RISK-005 | ML·인과·방문 보장 오인 | copy review와 F0-public-rule |

### 18.2 가정과 열린 질문

| ID | 내용 | 미해결 영향 |
|---|---|---|
| ASM-001 | F0는 공개 데이터로 독립 실행 가능하다. | 실제 데이터 접근은 DATA 게이트 전 미확정 |
| ASM-002 | 이동시간은 검증값으로 제공될 수 있다. | 없으면 후보 제외·오류 |
| ASM-003 | candidate_id를 안정적으로 만들 수 있다. | 없으면 운영 결과 no-go |
| ASM-004 | 인증 없이 핵심 가치를 시험한다. | 게스트 경로가 필요 |
| OPEN-001 | 실제 공개 source, schema, licence, values, availability, vintage는? | 운영 결과·DATA gate |
| OPEN-002 | 비용 누락 후보를 남길지 비용도 하드 필터로 할지? | eligibility·ERR-COST-MISSING |
| OPEN-003 | 날짜·시간 커버리지와 시간대는? | 과거·지원 범위 |
| OPEN-004 | 공개 경로·이동시간 공급과 공간 매핑은? | 하드 필터 |
| OPEN-005 | 동일 조건 정의와 집계 기간은? | ranking basis |
| OPEN-006 | 지원 기기·플랫폼·breakpoint는? | responsive QA |
| OPEN-007 | Apple UI 유지와 게스트 진입 위치는? | Entry UX |
| OPEN-008 | 로컬/네트워크 실행과 offline 정책은? | NFR availability |
| OPEN-009 | 위치 로그·보존 기간·규칙 버전 형식은? | 개인정보·감사 |

## 19. F0 릴리스 / No-go 체크리스트

다음 중 하나라도 아니오 또는 증거 없음이면 F0 릴리스는 no-go다.

### 기능·규칙

- [ ] 네 입력과 오류, 날짜·시간 보수적 검증이 구현·검증되었다.
- [ ] 하드 필터가 랭킹보다 먼저 실행되고, 최대값 동일 경계가 검증되었다.
- [ ] 제외 후보가 Top 5·count·비교에 복귀하지 않는다.
- [ ] same-condition → global popularity → shortest travel time fallback과 candidate_id tie-breaker가 결정적이다.
- [ ] Top 5, 0개, 1~4개 결과와 empty가 실제 개수대로 동작한다.
- [ ] automatic condition relaxation이 없다.

### 데이터·투명성

- [ ] 실제 공개 source, schema, licence, values, availability, vintage, mapping의 DATA gate 증거가 있다.
- [ ] 숫자와 이유에 source·vintage·method가 연결되어 있다.
- [ ] source/vintage가 없으면 운영 결과를 표시하지 않는다.
- [ ] static destinations와 숫자가 fixture로 표시되거나 검증 데이터로 교체되었다.
- [ ] F0-public-rule, 실시간 아님, 개인화 아님, 인과 아님, 제한사항이 사용자에게 보인다.
- [ ] ML·학습·예측·방문 보장 표현이 없고, B078/B079·자격증명 없이 실행된다.

### 화면·상태·접근성

- [ ] 390×844에서 Splash, Entry, Home, Results, Info, Detail, Empty, Error가 잘리지 않는다.
- [ ] tabs와 back navigation이 올바른 입력·결과 상태를 보존한다.
- [ ] loading/조회 실패/offline에 무한 spinner·stale/fake fallback이 없다.
- [ ] 색상 없이도 선택·적격·오류·fixture를 알 수 있고, 포커스·스크린리더·reduced motion을 확인했다.

### 증거·운영

- [ ] 단위·통합·UI·접근성·데이터·콘텐츠 테스트 증거를 실제/제안으로 구분했다.
- [ ] 실제 성능·가용성 결과가 없으면 주장하지 않고 측정 목표만 기록했다.
- [ ] 백엔드·SSO·인증·분석 파이프라인·법적 승인·데이터 품질을 이미 확보했다고 주장하지 않는다.

## 20. 구현·테스트 인수인계

1. DATA-VAL 게이트와 fixture/운영 데이터 경계를 먼저 확정한다. 데이터가 없으면 fixture로 화면·규칙만 검증하고 운영 추천은 승인하지 않는다.
2. 하드 필터, basis 선택, tie-breaker, Top 5를 UI와 분리해 테스트한다.
3. 결과의 숫자는 표시 여부보다 source·vintage·method 연결 여부를 검증한다.
4. empty·오류·offline이 결과를 채우는 우회로가 되지 않는지 확인한다.
5. 이 문서가 정의하지 않은 API, 외부 데이터 값, 인증 동작, 백엔드 구조, 법적 승인, 성능 결과는 사실로 추가하지 말고 OPEN 질문 또는 별도 승인 문서로 갱신한다.
