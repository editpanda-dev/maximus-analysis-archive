# 막시무스 카페·공부 1·2번 수정 및 자체 검수

작성일: 2026-10-06. 담당: 장한별. 분석 단위: 서울 공식 상권 `area_code` 786개.

## 전달 결론

1번 명칭·상태 수정과 발견된 커버리지 분모 오류 정정을 수행했다. 수정 후 테스트 6개와 통합 계산이 통과했다. 2번은 환경 기록·고정 절차를 마련했지만 **성공한 Windows 분석 환경의 패키지 버전 파일을 아직 받지 못했으므로 완료가 아니다**. 이 문서는 현재 수행분의 검토본이며, 1·2번 전체 최종 완료본으로 표시하지 않는다.

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

### 확인된 실행 근거

- 사용자 Windows에서 Python **3.12.10** 설치 확인.
- 독립 분석 `.venv`에서 기존 테스트 **5개 통과**, 통합 실행 **PASS 14 / 미완료 조건 3** 확인.
- 수정 코드의 작성자 Linux 환경에서 기존 5개와 추가 근거 등급 검사 1개, **6개 통과**.
- API 서버용 `.venv`는 별도 환경이다. API 설치 로그의 FastAPI 등 버전을 분석 환경 고정에 가져다 쓰지 않는다.
- 위 결과는 성공한 기존 환경의 실행 근거이다. 정확한 버전 고정 파일로 새 Windows 환경을 재설치한 검증은 아직 없다.

### 아직 필요한 입력

성공한 분석 환경에서 생성한 **`requirements-windows-py312-lock.txt`**를 첨부해야 한다. 기존 `requirements_delivery.txt`는 직접 패키지 이름만 있어서 정확한 버전을 알 수 없다. 작성자의 Linux 버전을 사용자의 검증된 Windows 버전으로 대체하지 않는다.

가장 간단한 생성 명령(PowerShell):

```powershell
cd C:\work_maximus\maximus_cafe_study_oct06_20261003
.\.venv\Scripts\python.exe -m pip freeze | Out-File -Encoding utf8 requirements-windows-py312-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

생성된 TXT 파일과 `pip check` 결과를 전달한다. `.env`, API 키, 가상환경 폴더를 첨부할 필요가 없다.

추가 제공한 `scripts/capture_analysis_environment.py`를 분석 루트의 scripts에 넣어 실행하면 같은 잠금 파일과 `analysis-environment.json`에 Python·운영체제·아키텍처·패키지 버전을 함께 기록할 수 있다. 이 스크립트는 키나 환경변수를 읽지 않는다. 실행은 ` .\.venv\Scripts\python.exe -m scripts.capture_analysis_environment`이다.

### 고정 파일을 받은 뒤 완료할 검수

1. 패키지 명칭·정확한 버전·필수 의존성·Python/Windows 호환성과 직접 URL/로컬 경로 포함 여부 확인.
2. 필요하면 통합 실행·테스트용과 대형 OSM PBF 재추출용 의존성을 분리. 현재 작성자 환경에는 osmium이 없어 PBF 재추출 검증을 새로 수행했다고 주장하지 않는다.
3. 별도 검증 환경에 고정 파일로 설치하고 `pip check`, 6개 테스트, 통합 실행 확인. 새 Windows 환경 검증은 사용자 실행 결과도 확보.
4. 환경 JSON·고정 파일·검증 로그를 Git 제출물과 함께 보존.

확인 전에는 `environment_status=pending_windows_lock`이며 2번을 완료 처리하지 않는다.

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
| Windows 버전 고정 파일 | 미수신, 2번 완료 판단 보류 |

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

이번 문서와 수정 코드는 환경 입력과 후속 검수를 마친 뒤 표준 분석 브랜치로 공유할 대상이다. API 담당자의 `feature/api-env-study@b7b479ba` 작업과는 별개다. 키·.env·.venv와 무관한 교통 원천 ZIP 변경은 커밋 대상에서 제외한다.
