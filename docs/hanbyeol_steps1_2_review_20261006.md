# 막시무스 카페·공부 1·2번 수정 및 자체 검수

작성일: 2026-10-06. 담당: 장한별. 분석 단위: 서울 공식 상권 `area_code` 786개.

## 전달 결론

1번 명칭·상태 수정과 커버리지 분모 오류 정정, 2번 사용자 분석 환경의 정확한 버전 고정 파일 수신·반영을 완료했다. 같은 26개 버전을 새 Linux 환경에 설치해 의존성 검사, 테스트 6개 및 통합 실행을 검수했다. 이 문서는 **1·2번 수정 범위의 최종안**이다. 전체 10/6 과제 완료본이나 최종 공부 추천 점수표는 아니다.

팀 결정은 **S4 제외 공부 시설 접근성 기준선 v0**이다. 이번 단계에서는 그 결정을 기록했으며, S4 전수 검증을 v0 제출 조건에서 분리했다. 가중치 재정의와 점수 재산출은 후속 단계다. 기존 75% 부분 점수를 이미 확정된 v0이라고 이름만 바꾸지 않았다.

## 1. 보행 접근성의 정확한 의미

공유·발표용 표현:

> 현재 결과는 공식 상권 경계에서 시설 좌표까지의 OSM 보행망 기반 후보 접근성 분석이다. 일부 경로에는 직선 진입 연결 가정이 포함돼 있으며, 실제 출입구·현재 보행 허용 여부를 검증한 도보 추천은 아니다.

| 원본 route_status | 건수 | 전체 후보쌍 대비 | 수정된 해석 |
|---|---:|---:|---|
| inside_area | 813 | 8.0% | 내부 시설 거리 0m 집계 규칙. 실제 출입구 검증 아님 |
| routed | 108 | 1.1% | OSM 모델 계산, 시설 좌표–링크 간격 2m 이하. 실제 진입 가능성 검증 아님 |
| assumed_straight_entrance_connector | 7,165 | 70.7% | 2~30m 직선 진입 연결 가정을 포함한 잠정 경로 |
| 미해결 3상태 합계 | 2,046 | 20.2% | 경로/연결 미확보. 접근 불가 또는 시설 부재로 단정할 수 없음 |
| 합계 | 10,132 | 100.0% | 고유 상권–시설 후보쌍. 고유 시설 개수가 아님 |

미해결은 `no_route_within_700m` 1,511건, `no_pedestrian_edge_within_30m` 529건, `no_network_boundary_entry` 6건이다. 후보군은 원천 POI 중 상권 폴리곤까지 직선거리 600m 이하인 쌍이다. 후보쌍 밖을 실제 보행 API로 전수 검증했다는 뜻은 아니다.

### 실제 수정한 사항

| 대상 | 이전 문제 | 수정 |
|---|---|---|
| 최신 통합표 `walk_network_status` | 실제 OSM 계산 이후에도 미계산 문구가 남음 | `osm_candidate_accessibility_with_assumed_entrance_connectors`로 교체 |
| OSM 민감도 `method` | `verified_connector_le2m`가 실제 출입구 검증으로 읽힐 수 있음 | `osm_model_connector_le2m`로 변경 |
| 커버리지 표 `candidate_pairs_euclidean_600` | STRtree의 더 넓은 검색 범위 건수를 기록 | 실제 600m 필터 통과 상세표의 건수를 기록 |
| 근거 등급 표 | 원본 상태만으로 출입구 검증 여부를 구별하기 어려움 | `walk_evidence_class`, `actual_entrance_verified=false`, `current_legal_walk_verified=false` 추가 |
| 공부 목표 정의 | S4 포함 최종 점수와 후속 제출 목표 혼재 | S4 제외 v0 결정과 재가중 미실행 상태를 명시 |

커버리지 표의 이전 합계 **12,813**은 실제 상세표 **10,132**보다 **2,681**쌍 많았다. 거리 상세표 자체가 2,681쌍을 중복 포함한 오류는 아니며, 요약표 분모의 정의·계산 오류였다. 원본 비교값은 `coverage_denominator_correction_786.csv`에 남겼다.

원본의 `walk_access_400/500/600`과 `proxy_walk_access_*`는 값과 기존 파일 호환성을 유지한다. 전자는 내부 규칙 및 2m 이하 OSM 모델 경로에 한정된 판정이며, 법적·실시간·실출입구 보행 보증이 아니다. 직선 연결 가정과 미해결의 전자 플래그는 결측으로 남긴다. `certified`라는 기존 코드 내부 변형 이름 역시 이러한 모델 하한 진단을 뜻하는 이력 명칭이지 현장 인증이 아니다.

거리값·상권–시설 키·반경 포함 여부·점수 수식·순위는 이 단계에서 바꾸지 않았다. 786개 상권 모두에 커버리지 건수를 제공한다. 후보가 0인 상권도 **원천 후보군에서 0건**이라는 의미이며 시설 부재를 검증한 결과가 아니다. 미확인 쌍이 집계에서 빠진 모델 지원 건수는 실제 전체 시설 수와 구분해서 사용해야 한다.

## 2. 실행 환경과 버전 고정

| 근거 | 확인 결과 | 범위 |
|---|---|---|
| 사용자 Windows Python | 3.12.10 | 사용자 실행 로그 |
| 사용자 기존 분석 테스트 | 5개 통과 | 이전 제출 코드 |
| 사용자 pip check | No broken requirements found. | 기존 Windows 환경 의존성 충돌 없음 |
| 수신한 lock 파일 | 26개 패키지 모두 정확한 버전 지정 | 로컬 경로·직접 URL 없음 |
| 독립 신규 환경 | Linux Python 3.12.14 | 사용자 Windows를 직접 조작한 결과 아님 |
| 독립 신규 설치 버전 비교 | 26개 전부 lock과 일치 | Windows 전용 바이너리 설치 검증은 별도 |
| 독립 pip check | No broken requirements found. | 신규 환경 의존성 충돌 없음 |
| 수정 코드 회귀 테스트 | 6 passed in 1.64s | 기존 5개 + 근거 등급 1개 |
| 통합 실행 | PASS 14, BLOCKED 3 | 기존 경로 입력으로 재계산 |

저장소 루트에 `requirements-windows-py312-lock.txt`를 추가했다. 사용자 첨부 내용과 패키지·버전은 동일하며 UTF-8 BOM/줄바꿈만 정리했다. 환경 검수 근거는 `data/processed/cafe_study_taxonomy/steps1_2_20261006/environment_validation_20261006.json`에 기록했다. API 서버용 가상환경의 패키지는 섞지 않았다.

`pip check`는 의존성 충돌 검사다. 경로 정확성·시설 근거·통계적 적합성을 검증하는 명령은 아니다. 새 환경 설치는 독립 Linux에서 수행했으며 **새 Windows 환경 재설치 검증은 아직 수행하지 않았다**. osmium 설치는 확인됐지만 OSM PBF 전체 재추출은 이번 검수에 포함하지 않았다.

### 팀원이 Windows에서 재현하는 순서

아래 명령은 이번 수정 코드와 고정 파일이 있는 저장소 루트에서 실행한다. 기존 ZIP 폴더에 수정 파일이 자동 반영되는 것은 아니다. 기존 `.venv`는 그대로 두고 별도 `.venv-repro`를 만든다.

```powershell
py -V:3.12 -m venv .venv-repro
.\.venv-repro\Scripts\python.exe -m pip install -r requirements-windows-py312-lock.txt
.\.venv-repro\Scripts\python.exe -m pip check
.\.venv-repro\Scripts\python.exe -m scripts.audit_hanbyeol_steps1_2
.\.venv-repro\Scripts\python.exe -m pytest -q tests/test_hanbyeol_walk_access.py tests/test_prepare_hanbyeol_steps_1_3.py tests/test_hanbyeol_oct06_integration.py tests/test_hanbyeol_route_evidence_labels.py
.\.venv-repro\Scripts\python.exe -m scripts.build_hanbyeol_20261006_integration
```

기대 결과는 의존성 충돌 없음, 테스트 6개 통과, 통합 QA PASS 14와 미완료 조건 3개다. 이 3개를 없애려고 근거가 없는 데이터를 정상으로 바꾸지 않는다.

## 3. 자체 검수 결과 및 실행 범위

| 검수 항목 | 결과 |
|---|---|
| 상세표 행수·고유 area_code/place_id | 10,132행, 중복 없음 |
| 네트워크 모델/가정/미해결 건수 | 921 / 7,165 / 2,046 일치 |
| 미해결 거리와 모델 판정 결측 | 유지 |
| 실제 출입구·현재 보행 허용 검증 주장 | 모든 행 false로 명시 |
| 원래 거리·접근성 플래그 변경 | 없음 |
| 상권별 정확한 후보쌍 분모 | 786행, 합계 10,132 |
| 통합 실행 | PASS 14, 기존 미완료 조건 3 유지 |
| 테스트 | 6개 통과 |
| 버전 고정·독립 신규 설치 | 26개 정확한 버전 일치, pip check 통과 |

재현 명령:

```bash
python -m scripts.audit_hanbyeol_steps1_2
python -m scripts.build_hanbyeol_20261006_integration
python -m pytest -q tests/test_hanbyeol_walk_access.py tests/test_prepare_hanbyeol_steps_1_3.py tests/test_hanbyeol_oct06_integration.py tests/test_hanbyeol_route_evidence_labels.py
```

이번 검수는 기존 거리 입력으로 수행했다. 새 카카오 호출, OSM 재다운로드, 출입구 현장 검증, v0 점수 재가중, 팀 공통 거리 통일, 최신 식사 버전 결합은 수행하지 않았다. 원본 10/3 통합표의 식사 입력은 `d0b6734` 스냅샷이며 10/6 최신 식사 결과와 혼동하지 않는다. HTTP 200 추천 응답도 도보 후보쌍 전수 검증 근거로 사용하지 않는다.

## 4. 결과 파일과 근거

- `data/processed/cafe_study_taxonomy/steps1_2_20261006/walk_evidence_labels_10132.csv`: 근거 등급·실출입구 검증 상태.
- 같은 폴더 `walk_evidence_coverage_786.csv`: 정확한 분모와 상권별 모델/가정/미해결 건수.
- 같은 폴더 `coverage_denominator_correction_786.csv`: 이전·정정 분모 비교.
- 같은 폴더 `steps1_2_qa.json`: 건수·환경 입력 상태·S4 제외 결정.
- OSM 커버리지·민감도와 최신 통합표: 표시·분모 정정 반영.
- `scripts/audit_hanbyeol_steps1_2.py`, `scripts/capture_analysis_environment.py`: 재현 및 환경 기록.

원천 버전: 분석 입력 로컬 커밋 `9c80c6c673b9164a34510c6fa70a8ef7b7ad0439`, Geofabrik OSM 2026-10-02, 카페 `6c591a7`, 기존 식사 `d0b6734`, 카카오 경로 `f2846ce`. 공식 상권과 POI 출처·라이선스·좌표 처리 설명은 `hanbyeol_oct06_execution_20261003.md`, `study_poi_source_and_taxonomy.md` 및 taxonomy 문서에 있다. OSM 기여자와 ODbL 조건을 유지한다. 기존 source commit은 GitHub에서 조회되지 않는 로컬 커밋이며 원격 전달 완료로 표현하지 않는다.

이번 문서와 수정 코드는 로컬 분석 브랜치에 커밋할 대상이며 원격 푸시·main 통합은 이번 단계에서 수행하지 않았다. API 담당자의 `feature/api-env-study@b7b479ba` 작업과는 별개다. 키·.env·.venv와 무관한 교통 원천 ZIP 변경은 커밋 대상에서 제외한다.

## 5. 남은 과제와 공유 상태

- S4를 제외한 공부 시설 접근성 기준선 v0 가중치 확정·재산출. 기존 75% 부분합을 최종 공부 점수로 쓰지 않는다.
- 김건우님 식사 결과와 카페·공부의 접근성 정의·비교 모집단 통일 후 조합 재계산.
- 카페 complete 224개와 supply_only·insufficient 순위를 구분. 224개 Top10을 786개 전체 순위로 표시하지 않는다.
- 보행 출입구 연결 가정과 미해결 경로는 이번 환경 검수로 해결되지 않았다.
- 공유 브랜치에 실제 푸시하고 팀원이 해당 커밋을 조회하도록 확인. 로컬 커밋은 원격 공유 완료와 다르다.

1·2번 검수 범위에서 추가 발견된 오류는 없다. 자료의 미검증 부분과 위 후속 과제는 남아 있다.
