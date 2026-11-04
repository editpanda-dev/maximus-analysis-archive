# 카페·공부 taxonomy 피드백 반영 및 10/6 점수 산출 전 진단

작성일: 2026-09-29 · 기준 브랜치: `codex/integrate-study-public-facilities` · 재현: `python scripts/analyze_hanbyeol_cafe_study_v1_draft.py`

이 문서는 [9/29 taxonomy](hanbyeol_cafe_study_taxonomy_20260929.md)의 추가 업무에 대한 실행 결과다. **보행 네트워크 자료가 아직 없어 보행거리 점수와 최종 공부 v1 Top 10은 산출하지 않았다.** 수치가 있는 분석은 `2025년 4분기` 공식 점포·추정매출과 `2026-09-18/21` POI 스냅샷의 **현재 기준선 진단**이다. 이 시점 혼합으로 2025년 예측 성능을 주장하지 않는다.

## 1. 결과 요약

| 보완 항목 | 이번 실행 결과 | 10/6 반영 판단 |
|---|---|---|
| 보행 네트워크 | 실제 도로·보행로 그래프 **미확보**. 경계에서 POI까지 네트워크 최단경로 계산 스크립트·입력 규격·빈 결과 스키마 마련. 합성 선분의 경계 출발 거리 200m 테스트 통과 | 원천과 출입구 연결 QA 후 400/500/600m 전수 실행. 현재 값은 `euclidean_legacy`만 존재 |
| S3a/S3b | 현재 백분위 신호 스피어만 **0.491**. 기존 30%+15% 대비 카카오 스터디카페에 45%를 주면 Top 10 **70%**, 둘의 max 45%는 **50%** 유지 | 우선안: S3a를 주 공급 프록시, S3b는 진단 열. 45% 재배분은 **시험안**, S4 검증 전 공부 v1 미발표 |
| C_stay/S4 | 스타벅스 키워드 414건 + OSM 대형카페 13건 = **427개 검토 후보**. 모두 `decision=unknown`, 인용·검토자 없는 확인 판정 **0건** | 범위가 전체 카페를 포괄하지 않으므로 최종 S4 구성값과 공부 v1 점수는 NA |
| 직선거리 인접 가중치 | **기존 공공시설 성분만** `inside`, `inside+0.25×nearby`, `inside+0.50×nearby` 비교. 0.25 대비 Top 10 공통 비율 각각 **60%, 100%, 80%** | 0.25가 안정적이라고 판정 불가. 보행거리로 다시 계산 후 선택 |
| 면적 보정 | 아래 2절. 절대 수 카페 점수와 면적 스피어만 0.753, 잔차는 -0.005. Top 10 대폭 교체 | 규모 보정 필요. 잔차는 후보 방식이며 최소 표본·실제 시설 근거와 함께 비교 |
| 매출 결측·순위 | 786개 중 카페 2개 업종 매출 모두 관측·비중 계산 가능 **224**(complete), 두 업종 매출행 없음 **232**(supply_only), 일부만 관측 또는 공급 부족 **330**(insufficient) | `full_score`는 complete 224개 안에서만, `supply_only_score`는 해당 232개 안에서만 별도 정렬 |
| 관광특구 | 원본 786행 유지, 광역 관광특구 **6개**에 추천 참고용 제외 사유 부여 | 세부 상권의 추천 자격은 유지. Top 10 분모·대상 표시 |

Top 10 공통 비율은 10개 `area_code`의 교집합/10이다. 동점은 `area_code` 오름차순으로 정렬해야 비교가 결정적이다. 현재 카페 점수는 `제과점`을 카페에 넣은 **시험안**이며 식사 점수의 동일 업종 제외가 팀 전체 코드에 아직 반영되지 않았다. 이 시험안을 최종 목적 조합에 섞지 않는다.

## 2. 상권 규모 보정: 같은 공식 업종을 네 방식으로 비교

`절대 수`, `점포 수/max(area_km2,0.02)`, `업종 점포 비중/서울 전체 업종 비중`, `log1p(점포 수) ~ log(max(면적,0.02)) + log1p(전체 점포 수)`의 **잔차**를 비교했다. 서울 평균 분모는 2025년 4분기 점포 원시자료의 서울 상권 전체이며, 잔차 회귀의 적합 모집단은 접근 가능한 786개다. 상관계수는 786개 전체에서 계산했다. Top 10은 극소 표본 쏠림을 막기 위해 카페 `해당 업종 점포≥10, 전체 점포≥50`(327개), 독서실 `해당 업종 점포≥3, 전체 점포≥50`(114개)에서만 비교했다. 이 최소치 자체도 시험 기준이다.

| 업종·방식 | 상권 면적과 스피어만 | 전체 점포 수와 스피어만 | 절대 수 Top 10과 교집합 |
|---|---:|---:|---:|
| 카페(커피·제과) 절대 수 | 0.753 | 0.807 | 10/10 |
| 카페 면적당 밀도 | 0.183 | 0.479 | 1/10 |
| 카페 서울 업종 특화도 | 0.194 | 0.002 | 0/10 |
| 카페 잔차 | -0.005 | 0.033 | 0/10 |
| 공식 독서실 절대 수 | 0.453 | 0.491 | 10/10 |
| 공식 독서실 면적당 밀도 | 0.271 | 0.345 | 2/10 |
| 공식 독서실 서울 업종 특화도 | 0.270 | 0.274 | 1/10 |
| 공식 독서실 잔차 | -0.042 | -0.047 | 7/10 |

카페 잔차 회귀의 표본 내 R²는 **0.715**, 독서실은 **0.294**다. 잔차의 면적 상관이 0에 가까운 것은 같은 표본에서 면적을 설명변수로 적합했기 때문에 기대되는 성질이며, **추천 품질이나 외부 검증 성공의 증거가 아니다.** 특화도 단독 정렬에서는 점포가 1~2개인 소형 상권이 최상단에 나타나 최소 표본 제한을 적용했다. 상권 밀도는 경계 면적 정의에 민감하며 관광특구는 참고용으로 따로 표시한다. 개별 카카오 스터디카페 POI에는 서울 전역 동일 방식으로 수집한 전체 업종 분모가 없으므로 이를 공식 독서실의 특화도로 대체하지 않는다.

## 3. C_stay·S4 재현 가능한 판정 규칙

`data/processed/cafe_study_taxonomy/c_stay_s4_evidence_review.csv`의 필수 열은 `place_id`, `place_name`, `evidence_source_url`, `evidence_quote`, `seat_verified`, `study_allowed_verified`, `mandatory_purchase`, `reviewer`, `reviewed_at`, `decision`이다. `source_dataset`, `candidate_source_url`은 추적용 추가 열이다. 초기 427행은 검토 완료가 아니라 **검토 대기열**이다.

1. 원천 상세 페이지·시설 운영자 안내 등에서 **좌석 존재를 명시**하면 `seat_verified=yes`; 좌석이 없다고 명시하면 `no`; 나머지는 `unknown`. 넓은 면적, Wi-Fi, 브랜드만으로 `yes`가 되지 않는다.
2. 학습·노트북·장시간 이용 허용 중 하나에 대한 **명시적 근거**가 있으면 `study_allowed_verified=yes`; 명시적 금지는 `no`; 나머지는 `unknown`. 제3자 리뷰만 있는 경우 근거 수준을 별도 검토하고 운영자 허용처럼 서술하지 않는다.
3. `C_stay`는 `seat_verified=yes` + URL·짧은 근거 내용·검토자·검토시점이 모두 있는 경우만 확인한다. `S4`는 여기에 `study_allowed_verified=yes`까지 필요하다. `mandatory_purchase`는 이용 조건으로 병기하며 알 수 없으면 `unknown`이다.
4. `decision` 허용값은 `verified_stay`, `verified_study`, `explicitly_not_suitable`, `unknown`이다. `verified_study`는 `verified_stay`도 충족한다. 시설 ID 중복 후보는 한 시설로 연결하고 검토 이력을 보존한다. 증거가 사라지거나 시점이 오래되면 재검토한다.
5. 빈 인용 또는 미확인 URL 상태의 427행은 모두 `unknown`. 이 표를 채우기 전에는 `study_v1_score=NA`, `study_v1_status=incomplete_stay_evidence`로 둔다.

## 4. 보행거리 전환 설계와 현재 막힌 입력

공식 상권 폴리곤의 **경계**와 실제 보행 가능 도로·보행로가 만나는 지점을 출발점으로 삼는다. 폴리곤 안 시설은 `walk_distance_m=0`. 밖 시설은 보행 그래프의 경계 교차점부터 연결된 경로 길이와 POI의 보행로 연결 길이를 계산한다. 400m는 초당 1.2m에 약 **5.56분**, 500m는 **6.94분**, 600m는 **8.33분**이다. 400m 후보는 직선거리 630m 이내로 먼저 좁히되, 이는 최종 합격 기준이 아니다. 배리어·접근 제한·교량·횡단 가능한 연결은 네트워크 구축 단계에서 처리해야 한다.

- 제안 입력: [Geofabrik 한국 OSM PBF](https://download.geofabrik.de/asia/south-korea.html) 같은 출처의 **날짜가 기록된** 보행 가능 경로를 추출한다. 보행로·도로의 실제 연결성과 보행 접근 제한을 반영해 EPSG:5186 `nodes.csv`(`node_id,x,y`)와 `edges.csv`(`u,v,geometry_wkt,length_m,oneway_walk`)로 변환한다. 현재 스크립트는 양방향 보행 간선만 지원하며 일방통행 보행 간선은 오류로 중단한다. 경로망 추출·검증을 생략한 임의 도로 중심선은 입력하지 않는다.
- `python scripts/build_hanbyeol_walk_access.py --nodes <nodes.csv> --edges <edges.csv> --network-source <명칭> --network-snapshot-date <YYYY-MM-DD>`로 계산한다. 상권 경계와 간선 교차점을 출발점으로 사용하는 방식이다. POI가 도로로부터 30m 이내일 때 가장 가까운 간선에 연결하며, 이 **연결 구간은 지도상 직선 추정**이다. 스냅 간격이 2m를 넘으면 `route_status=needs_entrance_connector_validation`과 접근 여부 `unknown`으로 남긴다. 출입구까지 실제 보행 가능한 연결을 검수한 뒤에만 최종 판정에 사용한다. 네트워크 거리 자체도 실제 보행시간의 보증이 아니다.
- 출력 설계: `walk_network_area_poi_access.csv`의 `area_code,place_id,walk_distance_m,walk_access_400,walk_access_500,walk_access_600,snap_gap_m,network_source,network_snapshot_date,route_status,euclidean_legacy_distance_m`. 400/500/600m의 **연결이 확인된** 시설 접근과 상위권 공통 비율은 `walk_radius_sensitivity.csv`로 산출한다. 기존 직선거리 집계는 `adjacency_weight_euclidean_legacy_*.csv`에 남긴다.
- **현재 `walk_network_access_pending.csv`와 `walk_radius_sensitivity_pending.csv`는 헤더만 있는 상태 표시용 파일**이다. 실제 보행 경로·상권별 네트워크 거리·400/500/600m Top 10 수치는 아직 없다. 그래프 입력이 마련되면 이 파일을 실제 결과로 대체하는 것이 아니라 별도 `walk_network_area_poi_access.csv`와 `walk_radius_sensitivity.csv`를 생성한다.

OSM 보행로 태그는 실제 연결 노드와 접근 권한에 따라 길찾기 가능성이 달라진다. 표면상 가까운 두 선분을 연결하면 안 된다. 데이터 출처의 ODbL 조건도 확인한다.

## 5. 데이터 파일과 QA

| 파일 | 의미 |
|---|---|
| `cafe_study_score_draft_786.csv` | 786행. 관광특구 자격·이유, 카페 `full_score`, `supply_only_score`, `score_status`/관측 플래그, 공부 v1 미완성 상태, 기존 공부 프록시 구분 |
| `s3a_s3b_proxy_comparison_786.csv`, `s3a_s3b_proxy_summary.csv` | 동일 기타 신호 아래 30+15 / S3a 45 / max 45 비교; 최종 검증된 공부 점수 아님 |
| `adjacency_weight_euclidean_legacy_786.csv`, `adjacency_weight_euclidean_legacy_summary.csv` | 직선거리 기존 공공시설 성분에 한정한 0/0.25/0.50 민감도 |
| `cafe_size_correction_786.csv`, `cafe_size_correction_summary.csv` | 카페 공식 점포 4방법·상관·Top 10 |
| `study_room_size_correction_786.csv`, `study_room_size_correction_summary.csv` | 공식 독서실 점포 4방법·상관·Top 10. 카카오 스터디카페와 동일 시설 수로 합산 금지 |
| `c_stay_s4_evidence_review.csv` | 427개 검토 대기 후보; `verified` 0건 |
| `walk_network_access_pending.csv`, `walk_radius_sensitivity_pending.csv` | 실측값이 없음을 드러내는 빈 스키마; 랭킹 입력 금지 |

재검토 결과 786행·고유 `area_code`, 공공 POI 268행·고유 장소 ID, 카카오 852+414행, 업종 코드 대조, 기존 공공시설 `inside≤buffer` 및 `nearby=buffer−inside`, 비완전 카페의 `full_score=NA`, 공부 v1 점수 전행 NA, 증거 검토 427행 전부 `unknown`을 확인했다. 보행경계 계산은 합성 네트워크의 200m 경로와 그래프 연결 없음 사례로 검사했다. 공식 점포·매출 파일의 집계 단위는 `분기×상권×업종`, POI 원천은 `장소×스냅샷`; 매출행 미공개를 관측 0으로 바꾸지 않는다.

**남은 실제 작업:** 보행 네트워크 원천 확보·변환 및 출입구 연결 검수, 400/500/600m 네트워크 표 전수 생성, C_stay/S4 근거 확인, 제과점 식사 이관에 대한 팀 합의, 새 보행거리를 적용한 점수·Top 10 재산출. 현재 표의 상위권은 이 작업을 대신하지 않는다.
