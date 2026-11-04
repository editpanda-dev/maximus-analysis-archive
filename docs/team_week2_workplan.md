# 막시무스 — 현재 상태 및 이번 주 병렬 작업 계획

기준일: 2026-09-21
팀원: 지우진 · 최시현 · 장한별

## 1. 프로젝트 현재 정의

동대문구 내 버스정류장과 지하철역 334개를 출발지로 두고, 대중교통 30분 안에 도달 가능한 공식 상권 폴리곤을 먼저 추린다. 이후 상권의 업종 구성, 시간대별 매출, 체류 시설, 이동 패턴을 결합해 식사·카페·공부·쇼핑·여가문화 목적에 맞는 상권을 비교하는 분석 기준선을 만드는 것이 현재 목표다.

현재 산출물은 개인별 실제 방문 목적이나 최종 추천 성능을 주장하는 모델이 아니다. 접근 가능한 후보군을 만들고, 상권의 목적 적합도를 투명한 규칙으로 비교하는 기준선이다.

## 2. 현재까지 완료된 내용

| 구분 | 완료 내용 | 주요 산출물 |
|---|---|---|
| 출발지 | 동대문구 버스정류장·지하철역 334개 좌표 구축 | `data/external/odsay_origins.csv` |
| 접근성 | 오전 8시, 오후 2시, 오후 7시 기준 30분 도달 정류장·행정동 계산 | `data/processed/local_transit_30min/` |
| 후보 상권 | 세 시간대 모두 출발지 25% 이상에서 접근 가능한 공식 상권 786개 도출 | `data/processed/commercial_area_accessibility/` |
| 상권 피처 | 2025년 점포 수·추정매출·시간대 매출을 공식 상권에 결합 | `data/processed/commercial_area_purpose_features/` |
| 기본 순위 | 식사·카페·쇼핑·여가문화 PATH-v0 규칙기반 순위 생성 | `official_area_purpose_latest_rankings.csv` |
| 공부 재정의 | 문구·서적·학원은 제외하고 체류형 학습으로 정의 | `scripts/build_commercial_area_purpose_features.py` |
| 공부 POI | 카카오 장소 검색으로 스터디카페 852개, 스타벅스 414개 수집·공간결합 | `data/external/kakao_study_stay_pois_20260918.csv` |
| 공부 보조순위 | 독서실·카페·스터디카페·스타벅스·접근성 결합 | `data/processed/study_stay_poi_enrichment/` |
| 공공 학습시설 | 원천 268개 중 공개 접근이 확인된 공공도서관·열람실·청년공간 236개를 상권 내부·400m 인접 피처로 결합 | `data/processed/study_public_facility_features.csv` |
| 공부 보조순위 통합 | 카카오 POI와 공공 학습시설을 중복 없이 결합한 현재 스냅샷 순위 재산출 | `codex/integrate-study-public-facilities` |

### 현재 목적별 top 10

| 순위 | 식사 | 카페 | 공부 | 쇼핑 | 여가문화 |
|---:|---|---|---|---|---|
| 1 | 광화문역 | 북촌(안국역) | 회기시장 | 롯데백화점(시청광장 지하쇼핑센터) | 수유역 |
| 2 | 종각역 | 서촌(경복궁역) | 사가정역 | 동대문패션타운 관광특구 | 방이동먹자골목 |
| 3 | 도화동 상점가 | 배화여대(박노수미술관) | 대학로(혜화역) | 동대문역사문화공원역 | 잠실새내역 |
| 4 | 대학로(혜화역) | 삼청동 | 이화여대 3·5·7길 상점가 | 강변역(테크노마트) | 군자역 |
| 5 | 을지로입구역 | 광화문역 | 종각역 | 종로3가역 | 길동역 |
| 6 | 북창동(시청역 6번) | 서교동(홍대) | 한성대입구역 | 잠실역 | 성신여대 |
| 7 | 남영동 먹자골목 | 경의선책거리 | 성신여대 | 강남 마이스 관광특구 | 상봉역 |
| 8 | 방이동먹자골목 | 을지로입구역 | 시영B상가 | 용산전자상가(용산역) | 구의역 |
| 9 | 서대문역 | 시청역 8번 | 뚝섬역상점가 | 남대문시장(자유상가) | 건대입구역(건대) |
| 10 | 이태원(이태원역) | 대학로(혜화역) | 한양대앞상점가 | 천호역 | 상계역 |

## 3. 현재 한계와 이번 주 제외 범위

- B078 원본은 오프라인 분석실 방문이 필요하다. 이번 주에는 B078을 입력 데이터·검증 데이터·발표 근거로 사용하지 않는다.
- 따라서 개인 단위의 방문 목적, 실제 목적지 선택 확률, 추천 정확도를 주장하지 않는다.
- 현재 공부 순위의 스터디카페·스타벅스 정보는 2026-09-18 현재 스냅샷이다. 2025년 매출 예측이나 과거 성능 검증에는 사용하지 않는다.
- 이번 주에는 앱 개발, LLM 파인튜닝, 개인화 모델 학습을 진행하지 않는다.

## 4. 이번 주 공통 목표

786개 접근 가능 공식 상권에 대해 접근성·상권구조·체류 POI·집계 이동목적을 각각 독립 피처로 구축한다. 결과적으로 다음 주에는 상권 코드(`area_code`) 기준으로 결합 가능한 피처 마트를 만든다.

이번 주 완료 기준:

1. 상권별 집계 이동목적·시간대 피처
2. 접근성 기준 변화에 대한 후보군·순위 안정성 검증
3. 공공 학습시설 POI 피처
4. 각 결과물의 원천, 기준일, 공간 단위, 한계를 설명한 README

## 5. 역할 분담

세 작업은 서로의 완료를 기다리지 않는다. 각자 원천 데이터부터 독립적으로 수집·정리·검증하고, 마지막에 `area_code`만으로 결합한다.

### 지우진 — 집계 이동목적 피처

#### 담당 범위

공개 서울 생활이동 데이터에서 시간대·출발지·도착지·집계 이동목적을 추출한다. 생활이동의 목적은 출근·등교·귀가·쇼핑·병원·관광·기타로 구성되며, 식사·카페·공부를 직접 뜻하지 않는다. 따라서 이 데이터는 추천 점수의 정답 라벨이 아니라 상권 이동 성격을 설명하는 외부 피처로 사용한다.

#### 작업 순서

1. 생활이동 원천의 단위, 기간, 목적 코드, 공간 코드, 시간대 코드를 정리한다.
2. 출발지 또는 도착지가 서울인 자료만 남긴다.
3. 동대문구 출발 흐름 및 후보 상권이 포함된 도착 행정동 흐름을 집계한다.
4. 행정동별 목적 비중과 시간대별 유입량을 계산한다.
5. 기존 상권-행정동 중첩 테이블로 행정동 피처를 상권 폴리곤 피처로 변환한다.

#### 예정 산출물

아래 경로는 **지우진 브랜치에서 새로 생성할 경로**다. 현재 기준 브랜치에 없으므로, 기존 파일과 혼동하지 않는다.

```text
data/external/living_movement/
data/processed/living_movement/
scripts/build_living_movement_features.py
docs/living_movement_data_dictionary.md
```

필수 결과 파일:

```text
official_area_living_movement_features.csv
```

필수 컬럼 예시:

```text
area_code
time_slot
commute_share
school_share
return_home_share
shopping_share
tourism_share
hospital_share
other_share
inflow_count
source_period
```

#### 완료 기준

- `area_code` 기준 786개 후보 상권 중 매핑 가능 상권 수를 보고한다.
- 목적별 비중의 합이 1인지 검증한다.
- 개인 이동이나 식사·카페·공부 목적을 직접 관측한 데이터가 아니라는 한계를 문서에 명시한다.

### 최시현 — 접근성·순위 안정성 검증

#### 담당 범위

25%, 50%, 80% 접근성 기준을 바꿨을 때 후보 상권과 목적별 상위 상권이 얼마나 달라지는지 검증한다. 목표는 25% 기준이 임의의 숫자가 아니라 탐색 범위를 넓게 잡기 위한 기준이며, 더 엄격한 기준에서도 결과가 얼마나 유지되는지 보이는 것이다.

#### 작업 순서

1. 25%, 50%, 80% 기준별 공식 상권 후보군을 재생성한다.
2. 각 기준의 후보 상권 수와 상호 교집합을 계산한다.
3. 식사·카페·쇼핑·여가문화 top 10을 기준별로 재산출한다.
4. 기준별 top 10 교집합 비율과 Jaccard 유사도를 계산한다.
5. 25%에서는 포함되지만 50% 또는 80%에서 빠지는 상권을 경계 후보로 분류한다.

#### 예정 산출물

아래 경로는 **최시현 브랜치에서 새로 생성할 경로**다. 현재 기준 브랜치에 없으므로, 기존 접근성 결과 파일을 덮어쓰지 않는다.

```text
data/processed/accessibility_sensitivity/
scripts/analyze_accessibility_sensitivity.py
docs/accessibility_threshold_validation.md
```

필수 결과 파일:

```text
threshold_summary.csv
purpose_top10_stability.csv
boundary_candidate_areas.csv
```

#### 완료 기준

- 세 시간대 기준이 모두 적용됐는지 확인한다.
- 후보 수, 교집합, top 10 유지율을 표 하나로 정리한다.
- 공부는 현재 POI 스냅샷을 포함하므로, 이번 안정성 검증에서는 식사·카페·쇼핑·여가문화와 분리해 표기한다.

### 장한별 — 공공 학습시설 POI

#### 담당 범위

스터디카페·스타벅스와 겹치지 않는 공공·교육형 학습 체류시설을 수집한다. 대상은 공공도서관, 공공열람실, 청년 학습공간, 대학도서관 또는 공개 접근 가능한 대학 시설이다.

#### 작업 순서

1. 시설 데이터셋별 출처, 기준일, 라이선스, 좌표 제공 여부를 조사한다.
2. 시설명·주소·위도·경도·운영상태·시설유형을 표준 컬럼으로 변환한다.
3. 동일 시설의 중복 행을 제거하는 기준을 만든다.
4. 시설을 공공도서관·열람실·청년공간·대학시설로 분류한다.
5. 786개 상권 폴리곤 내부 및 경계 400m 이내 시설 수를 계산한다.
6. 공부 top 20 상권의 시설 위치를 지도에서 수동 점검한다.

#### 예정 산출물

아래 경로는 **장한별 브랜치에서 새로 생성할 경로**다. 현재 확인한 `마아악히무쓰.xlsx`는 검토용 전달본이며, 아직 원격 저장소 산출물이 아니다.

```text
data/external/study_public_facility_poi.csv
data/processed/study_public_facility_features.csv
scripts/build_study_public_facility_features.py
docs/study_poi_source_and_taxonomy.md
```

#### 현재 기준선과의 연결

현재 기준 브랜치의 공부 체류형 결과는 다음 파일을 사용한다.

```text
data/external/kakao_study_stay_pois_20260918.csv
data/processed/study_stay_poi_enrichment/official_area_study_stay_poi_features_current.csv
data/processed/study_stay_poi_enrichment/official_area_study_stay_enriched_current.csv
scripts/build_study_stay_poi_enrichment.py
docs/team_week2_workplan.md
```

장한별의 `study_public_facility_*` 파일군은 생성 완료됐다. 통합 브랜치에서만 `area_code`로 결합하며, 공통 기준 브랜치 병합 전까지 기존 기준선을 직접 수정하지 않는다.

필수 컬럼 예시:

```text
place_id
facility_name
facility_type
address
longitude
latitude
operation_status
source_name
source_url
snapshot_date
```

#### 완료 기준

- 원천별 수집 건수와 중복 제거 후 건수를 함께 기록한다.
- 상권별 내부·400m 이내 시설 수를 분리한다.
- 2025년 매출 검증 피처가 아니라 현재 공부 체류 추천을 위한 POI라는 점을 문서에 명시한다.

## 6. 병렬 작업 구조

```text
지우진   : 생활이동 원천 → 행정동/상권 이동목적 피처
최시현   : 도달 결과 → 접근성 기준별 후보군·순위 안정성
장한별   : 공공시설 원천 → 상권별 학습 체류 POI 피처

공통 결합 키: area_code
```

각자는 다른 사람의 결과 파일을 입력으로 사용하지 않는다. 마지막 통합 시점에만 세 결과를 `area_code`로 병합한다.

## 7. GitHub 운영 규칙

### 표준 산출물 파일명

이 표의 경로만 팀의 정식 산출물로 사용한다. 파일명에 `final`을 붙이지 않는다. 현재 데이터는 기준일이 있는 스냅샷이므로, `final`은 이후 갱신본과 구분할 수 없게 만든다.

| 구분 | 정식 경로 | 비표준 별칭 (사용 금지) |
|---|---|---|
| 현재 공부 체류 POI 원천 | `data/external/kakao_study_stay_pois_20260918.csv` | `study_stay_786_final.xlsx` |
| 현재 공부 체류 상권 피처 | `data/processed/study_stay_poi_enrichment/official_area_study_stay_poi_features_current.csv` | `study_stay_area_features_final.csv` |
| 현재 공부 체류 통합 피처 | `data/processed/study_stay_poi_enrichment/official_area_study_stay_enriched_current.csv` | — |
| 현재 공부 체류 생성 스크립트 | `scripts/build_study_stay_poi_enrichment.py` | `build_study_stay_final.py` |
| 장한별 공공 학습시설 원천 | `data/external/study_public_facility_poi.csv` | — |
| 장한별 공공 학습시설 상권 피처 | `data/processed/study_public_facility_features.csv` | — |
| 장한별 생성 스크립트 | `scripts/build_study_public_facility_features.py` | — |
| 장한별 출처·분류 문서 | `docs/study_poi_source_and_taxonomy.md` | — |

지우진·최시현의 예정 산출물도 각 담당 절의 경로와 파일명을 그대로 사용한다. 새 별칭을 만들지 않으며, 이름을 바꿔야 할 경우에는 먼저 이 표를 수정하고 같은 커밋에서 참조 문서도 갱신한다.

### 현재 상태

- 원격 저장소: `editpanda-dev/maximus-analysis-archive` (비공개)
- `main`: `b405034` — 786개 상권 매출·구조 괴리 분석까지 반영
- `codex/year-matched-purpose-mapping`: `b86f118` — 2025년 목적별 폴리곤 매핑과 기존 POI 반영
- `codex/study-stay-baseline`: `3295260` — 최신 공부 체류 순위·카카오 POI·관련 스크립트가 원격에 반영됨
- `codex/integrate-study-public-facilities`: 공공 학습시설 피처와 공부 보조순위 통합본. 검증 후 `codex/study-stay-baseline`에 병합 예정

팀의 공통 기준점은 `codex/study-stay-baseline` 브랜치다. 세 개인 브랜치는 이 브랜치에서 생성한다.

### 브랜치 이름

```text
codex/study-stay-baseline
codex/jiujin/living-movement
codex/sihyun/accessibility-sensitivity
codex/hanbyeol/study-public-poi
codex/integration-week2
```

### 브랜치 규칙

1. 개인 작업 브랜치는 반드시 `codex/study-stay-baseline`에서 만든다.
2. 다른 팀원의 개인 브랜치에서 분기하지 않는다.
3. 다른 팀원이 소유한 파일을 고쳐야 하면 직접 수정하지 않고 먼저 메시지로 공유한다.
4. 개인 브랜치에서는 본인 담당 폴더와 본인 문서만 수정한다.
5. 결과가 끝나면 `codex/study-stay-baseline`을 대상으로 PR을 만든다.
6. 세 PR 병합 후에만 `codex/integration-week2`에서 최종 피처 마트를 생성한다.

### 파일 소유권

| 담당 | 소유 폴더 |
|---|---|
| 지우진 | **예정** `data/external/living_movement/`, `data/processed/living_movement/`, `scripts/build_living_movement_features.py`, `docs/living_movement_data_dictionary.md` |
| 최시현 | **예정** `data/processed/accessibility_sensitivity/`, `scripts/analyze_accessibility_sensitivity.py`, `docs/accessibility_threshold_validation.md` |
| 장한별 | **예정** `data/external/study_public_facility_poi.csv`, `data/processed/study_public_facility_features.csv`, `scripts/build_study_public_facility_features.py`, `docs/study_poi_source_and_taxonomy.md` |

### 커밋 규칙

커밋 형식:

```text
<type>(<scope>): <what changed>
```

예시:

```text
data(living-movement): add destination purpose features
feat(accessibility): add threshold sensitivity analysis
feat(study-poi): add public learning facility features
docs(method): document purpose proxy limitations
test(study-poi): cover polygon facility aggregation
fix(accessibility): correct threshold overlap calculation
```

규칙:

1. 한 커밋에는 하나의 논리적 변경만 넣는다.
2. 스크립트를 새로 만들거나 수정하면 대응하는 테스트를 함께 추가한다.
3. 데이터 원천 수집, 피처 생성, 문서 수정, 무관한 코드 수정을 한 커밋에 섞지 않는다.
4. `.env`, API 키, 개인식별 가능 데이터, 오프라인 전용 데이터는 절대 커밋하지 않는다.
5. 대용량 원본은 커밋하지 않는다. 대신 출처 URL, 다운로드 기준일, 컬럼 사전, 재현 스크립트를 커밋한다.
6. 처리 결과는 재현에 필요한 요약 CSV만 커밋한다.

## 8. 공유 일정

| 시점 | 해야 할 일 |
|---|---|
| 작업 시작일 | 개인 브랜치 생성, 원천 데이터·작업 범위 공유 |
| 금요일 저녁 | 각자 중간 결과 CSV 1개와 README 초안 push |
| 일요일 | 코드·테스트·최종 결과 파일 push, PR 생성 |
| 월요일 | PR 병합 후 `codex/integration-week2`에서 `area_code` 기준 통합 |

## 9. 이번 주에 하지 않는 것

- B078 원본을 전제로 한 목적지 선택모형 학습
- 개인화 추천 성능 주장
- LLM 또는 RoBERTa 파인튜닝
- 앱 화면 구현
- 원천 데이터 없이 점수 가중치를 임의로 최적화하는 작업
