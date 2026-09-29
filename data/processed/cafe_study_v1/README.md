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

공개 OSM 한국 PBF 원천은 확인했지만 약 288MB이며, 현재 저장소에는 보행 가능한 노드·간선·출입구 연결 데이터가 없다. 따라서 이 폴더의 거리 값은 `euclidean_legacy_distance_m`만 제공한다. 실제 보행거리·400/500/600m 민감도는 보행망을 확보·검증한 별도 산출물에서 생성해야 한다.

## 재현

```bash
python3 scripts/build_cafe_study_followup.py
python3 -m pytest tests/test_build_cafe_study_followup.py -q
```
