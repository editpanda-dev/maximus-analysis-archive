# 카페·공부 v1 후속 진단

기준일: 2026-09-29  
대상: 30분 접근성 25% 기준 공식 상권 786개

## 산출물

- `c_stay_s4_evidence_review_20260929_input.csv`, `cafe_study_score_draft_20260929_input.csv`
  - 장한별의 2026-09-29 제출 초안을 버전 관리용 입력으로 보존한 파일이다.

- `c_stay_s4_review_queue_786_euclidean_legacy.csv`
  - 기존 427개 C_stay/S4 검토 대기 후보 가운데 786개 공식 상권 내부 또는 **직선거리** 400m 이내에 있는 340개 후보만 남긴 표다.
  - 내부 238개, 직선거리 400m 인접 102개다.
  - 직선거리 수치는 후보를 빠르게 줄인 이전 기준일 뿐이며, 최종 점수·추천에 사용하면 안 된다.
  - `walk_distance_m`, `walk_access_status`는 보행 네트워크 입력이 없어 `pending_walk_network`이다.

- `cafe_size_adjusted_score_draft_786.csv`
  - 2025년 4분기 카페 초안의 공급 부분을 `log1p(업종 점포 수) ~ log(상권 면적) + log1p(전체 점포 수)` 잔차 백분위로 교체한 진단용 점수다.
  - 매출이 모두 관측된 상권은 `cafe_size_adjusted_full_score`, 카페 매출이 없는 상권은 `cafe_size_adjusted_supply_only_score`로 분리한다.
  - 관광특구를 제외한 완전관측 랭킹 대상은 218개, 공급 전용 랭킹 대상은 232개다.
  - 최종 카페 추천 점수는 아니다. 제과점의 식사→카페 이관 및 보행 네트워크 적용이 팀 전체에서 확정되기 전의 비교용 초안이다.

- `cafe_study_followup_summary.json`
  - 행 수·공간 매핑·랭킹 대상 수를 저장한 감사 요약이다.

## 보행 네트워크 상태

카카오맵 도보 경로 REST API를 이용하는 `scripts/build_kakao_walk_access.py`를 추가했다. 상권 내부 POI는 0m로 처리하고, 상권 외부·직선거리 400m 후보는 선택된 공식 상권 폴리곤의 가장 가까운 경계점에서 POI까지 `route_mode=SHORTEST` 도보 경로를 조회한다. 이 경계점은 실제 출입구가 아닌 투명한 경계 프록시다.

API 키는 저장소에 넣지 않는다. 아래처럼 실행하면 동일 `place_id × nearest_area_code` 조합은 결과 CSV를 캐시로 재사용하며, 기본값으로 새 API 호출을 최대 900건으로 제한한다.

```bash
export KAKAO_REST_API_KEY='발급받은_REST_API_키'
python3 scripts/build_kakao_walk_access.py
```

생성되는 `c_stay_s4_review_queue_786_kakao_walk.csv`의 `walk_distance_m`을 사용해 400m·500m·600m 접근 여부를 판단한다. API 결과가 없는 행은 `route_status`를 유지하고 점수에 사용하지 않는다.

## 재현

```bash
python3 scripts/build_cafe_study_followup.py
python3 -m pytest tests/test_build_cafe_study_followup.py -q
```
