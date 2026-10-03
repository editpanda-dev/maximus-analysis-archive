# 10월 6일 카페·공부 최종 산출 시도와 제출 가능 범위

작성: 2026-10-03 · 대상: 동대문구 334개 출발지 조건을 통과한 서울 공식 상권 786개. 앞서 작성한 [1~7단계 통합 문서](hanbyeol_cafe_study_1_to_7_integrated_20261003.md) 이후 실제 보행망과 김건우님 식사 브랜치를 추가 확보하여 다시 실행했다. 본문에서 **최종**과 **탐색**을 구분한다.

## 새로 확보한 원천과 재현 경로

| 원천 | 버전·범위 | 사용 목적과 제한 |
| --- | --- | --- |
| [Geofabrik 대한민국 OSM 추출](https://download.geofabrik.de/asia/south-korea-261002.osm.pbf) | 2026-10-02 PBF, SHA-256 `114f36be9bc6f698c36388cbd78d8ab0a1f95ee466cfaad53fe9722a822f275b` | `scripts/extract_maximus_osm_walk_graph.py`로 상권 주변 보행 가능 **후보** 링크 557,912개·노드 496,135개 추출. OSM 기여자 표기와 [ODbL](https://www.openstreetmap.org/copyright) 조건 적용. 그래프 원본/추출 파일은 큰 임시 입력이며 저장소에 포함하지 않음 |
| 팀 카카오 보행거리 | `codex/kakao-walk-feature@f2846ce`, `c_stay_s4_review_queue_786_kakao_walk.csv` 340건 | **선택된 가장 가까운 상권 하나**와 카페 후보의 경계 출발점 경로. 238건 내부 0m, 외부 102건 경로 응답. 모든 상권·모든 시설의 보행거리 표가 아님 |
| 카페 면적 보정 초안 | `codex/hanbyeol/cafe-study-followup@6c591a7`, `cafe_size_adjusted_score_draft_786.csv` 786행 | 기존 카페 공급·소비 점수와 구별하여 잔차 보정 카페 점수를 병렬 비교. 아직 최종 채택 점수가 아님 |
| 김건우님 식사·쇼핑 | `codex/gunwoo/food-shopping-subtypes@d0b6734`, `official_area_food_shopping_size_neutral.csv` 786행 | `food_meal_score_v1`와 매출 공개 비율 결합. 2025Q4 매출과 2026-06 상가 좌표를 섞은 **현재 설명용** 신호. 공식 2025년 예측검증 입력으로 사용 금지. 직선거리 400m 공급 성분 포함 |
| 다른 식사 v1 대조 | `codex/geonwoo/meal-shopping-v1@1e01203`, 786×2행 | 제과점 제외·주점 여가 이관의 코드 정합 확인. 김건우님 자료가 지적한 크기 보정·결측 정의 차이가 있어 이 브랜치의 점수를 3목적 조합에는 사용하지 않음 |

위 팀 파일 네 개는 `data/external/team_branch_snapshots/`에 커밋 해시를 붙여 읽기 전용 스냅샷으로 보존했다. 두 식사 구현의 점수를 섞지 않았다. 원래 통합 실행에는 최신 카페 면적 보정 초안이 빠져 있었고, Git 브랜치 재대조 후 별도 비교로 추가했다. 로컬 카페 입력 CSV는 해당 브랜치의 `cafe_study_score_draft_20260929_input.csv`와 `area_code`별 값이 일치하지만 파일 바이트는 일치하지 않는다.

## 1. 실제 OSM 보행망 계산의 범위와 품질

`scripts/build_hanbyeol_osm_walk_access.py`는 공식 상권 경계가 OSM 보행 링크와 만나는 지점부터 시설에 가장 가까운 링크까지 네트워크 최단경로를 계산한다. **상권 내부 시설은 0m**다. 시설에서 링크까지의 거리가 2m 이하이면 경로를 `walk_access_400/500/600`에 기록한다. 2~30m는 진입 동선을 확인하지 못한 직선 연결이므로 `proxy_walk_access_*`에만 기록하고 확정 접근 여부는 `unknown`으로 둔다. 직선거리 600m를 넘는 쌍은 보행 600m 이내일 수 없어 빠른 탐색에서 제외한다.

| 판정 | 상권–시설 후보쌍 | 해석 |
| --- | ---: | --- |
| 상권 내부 또는 시설 연결 간격 ≤2m | **921** | 내부 813, 외부 경로 108. OSM 그래프 기준 경로값이 있음. 다만 OSM 자체의 보행로·횡단·출입구 완전성은 별개 |
| 연결 간격 2~30m 직선 가정 | **7,165** | 최단경로+가상 진입 간격의 잠정 거리. 확정 `walk_access_*`에는 반영하지 않음 |
| 경로·진입 연결 판단 불가 | **2,046** | 700m 이내 경로 없음 1,511, 근처 링크 없음 529, 상권 경계 진입 없음 6. 접근 불가라는 증거로 0 처리하지 않음 |
| **합계** | **10,132** | 후보 786상권×공공 POI 268건+카카오 1,266건 중 직선거리 600m 이하 쌍 |

카카오 별도 경로 340건은 400/500/600m에 각각 **323/333/338건**이 들어온다. OSM과 같은 상권·시설에서 외부 경로 길이가 둘 다 있는 81건의 절대 거리 차이는 중앙값 **33.7m**, 400m 포함 여부 불일치는 **6건**이다. 따라서 OSM의 2~30m 가상 연결을 카카오 검증 경로와 같은 확신도로 취급하지 않는다. 카카오 340건은 C_stay/S4 증거 후보 선별에만 쓰며 공부 학습시설 852건 전체의 경로를 대체하지 않는다.

원천 추출 규칙은 보행금지·사유/허가 출입을 제거하고 `footway`, `path`, `pedestrian`, `steps`, 주거·서비스·일부 일반 도로를 보행 후보로 포함한다. OSM 도로 태그만으로 보도 유무, 실시간 통제, 횡단·계단 연결, 건물 입구 위치를 완전히 확인할 수 없다. 그러므로 `walk_distance_m`은 **OSM 네트워크 추정치**, `proxy_walk_access_*`는 **출입구 가정이 추가된 민감도용 값**이다. 합법·실시간 도보 400m를 완전히 검증했다고 주장하지 않는다.

## 2. 공부 시설 근거와 점수 상태

이전 236개 공공 플래그 중 공개 접근·학습 가능 확인을 모두 통과한 후보는 216개다. 이 중 `listed_stale_unverified`가 21개여서 운영 상태 미확인 후보를 빼면 **195개**, 실제 운영시간이 있는 페이지(`active_page_with_hours`)까지 확인된 고신뢰 표본은 **16개**다. `listed_in_standard_data` 179개는 공개 표준자료 등재를 뜻하며 현재 운영시간을 입증하지 않는다. 세 집단을 같은 의미의 “공부 가능 시설”이라고 부르지 않는다.

카카오 `study_cafe` **852개**는 S3a 검색 후보이고, 공식 `CS200038` 독서실 S3b는 중복 위험 때문에 검증 열에 둔다. C_stay/S4 검토표 427개 중 카카오 기준 선택 상권 보행 400m 이내가 **323개**이지만 **427개 모두 `decision=unknown`**이다. 후보 URL은 출처 진입점일 뿐 좌석·장시간/노트북/학습 허용의 장소별 증거가 아니다. 확인형 S4 점수는 **0이 아니라 결측**이다.

검토용 `study_partial_75pct_proxy`는 S3a 45% + 공개·학습 후보 20% + 기존 접근성 10%의 부분 합이다. S4 25%는 채우지 않았다. `study_S4_missing_arithmetic_min/max_given_proxy`는 **같은 잠정 경로·후보 집단을 고정하고** S4가 0~100점 사이일 때의 산술 범위일 뿐 검증된 점수 구간이 아니다. 실제 `study_v1_final_score`는 786행 모두 NA다. 보행 반경(400/500/600m)과 인접 가중치(0/0.25/0.5)의 18개 조합은 탐색 민감도 표에 보존했지만, 상권별 진입경로와 S4가 미확인인 상태에서 Top 10 안정성을 최종 판단하지 않는다.

## 3. 식사+카페+공부 결과의 정확한 이름

김건우님 식사 점수의 매출 공개 비율 70% 이상, 카페 두 업종 매출 완전관측, 관광특구 제외를 모두 충족한 공통 모집단은 **208개 상권**이다. 이 집단 안에서 식사·카페·공부 **부분 프록시**를 각각 백분위로 바꾸고 동등 평균한 `meal_cafe_study_top10_exploratory.csv`와 Top 20, 786개 지도 속성을 생성했다.

탐색 Top 10은 종각역, 대학로(혜화역), 인사동, 건대입구역(건대), 을지로3가역, 홍대입구역(홍대), 을지로입구역, 숙대입구, 뚝섬역, 종로3가역 순이다. **이것은 10월 6일 최종 3목적 추천 Top 10이 아니다.** 식사 공급의 일부는 2026년 직선거리 좌표 기반, 공부는 S4 25% 미반영·보행 진입 가정·운영 미확인, 카페는 완전관측 224개 집단만 포함한다. 따라서 `meal_cafe_study_final_score`도 786행 전부 NA로 남겼다.

최신 카페 브랜치의 면적 보정 초안을 같은 모집단에 넣은 별도 탐색 Top 10/20도 생성했다. 추천 가능하고 카페 매출을 완전 관측한 218개에서 기존 카페 점수와 보정 초안의 Top 10은 **8개 일치**했다. 식사 매출 공개 비율 조건까지 통과한 208개에서 두 카페 버전의 3목적 **부분 점수** Top 10은 **10개 일치**했다. 이 수치는 해당 모집단과 미완성 공부 신호에 한정된다. 면적 보정 초안을 기존 카페 점수로 대체하지 않고 두 점수·순위를 나란히 남겼다.

## 4. 자체 검수와 다음 입력

`integration_qa.csv`는 **PASS 14건**, `BLOCKED_ROUTE` 1건, `BLOCKED_EVIDENCE` 1건, `BLOCKED_FINAL_SCORE` 1건이다. 786행·고유 키, 18×786 민감도 행, 상권–시설 중복 0, 400≤500≤600 포함 관계, 보행거리≥직선거리, 잠정 진입을 확정 접근으로 승격하지 않음, 카카오 340건 범위, 식사 786행, 최신 카페 초안의 상태 일치, 최종 점수 NA, 탐색 Top 20의 동일 모집단, 지도 786개를 확인했다. 보행 경계·무경로 및 잠정 진입 분리 단위검사 등 **5개 테스트 통과**.

최종 점수에 필요한 입력은 (1) 시설 실제 출입구와 보행 허용 링크의 연결 확인 및 도로/횡단 규칙 검수, (2) C_stay/S4 시설별 근거 URL·짧은 인용·검토자·검토일과 운영 확인, (3) 김건우님 식사 점수의 직선거리 공급 성분과 카페·공부 보행거리 정의를 통일한 공통 버전이다. 이 작업 후 동일 모집단의 최종 목적 백분위를 다시 계산해야 한다.

### 제출 파일

- `data/processed/cafe_study_taxonomy/osm_walk_20261002/walk_network_area_poi_access.csv`: 후보쌍의 네트워크 거리, 확정/잠정 접근, 상태, 직선거리 비교.
- `.../osm_walk_20261002/walk_route_area_coverage_786.csv` 및 `walk_radius_sensitivity.csv`: 상권별 경로 커버리지와 반경 비교.
- `data/processed/cafe_study_taxonomy/oct06_integration/c_stay_s4_review_priority_427.csv`: 카카오 경로를 붙인 검토 우선순위. 모두 `unknown`.
- `.../oct06_integration/cafe_study_meal_integrated_786.csv`: 식사·카페·공부 부분 신호와 최종 미산출 상태를 합친 표.
- `.../oct06_integration/study_walk_radius_weight_variants_786x18.csv`, `study_walk_radius_weight_top10_sensitivity.csv`: 반경·가중치 민감도.
- `.../oct06_integration/meal_cafe_study_top10_exploratory.csv`, `meal_cafe_study_exploratory_map_786.geojson`: **탐색용** 조합과 지도.
- `.../oct06_integration/meal_cafe_adjusted_study_top10_exploratory.csv`, `meal_cafe_adjusted_study_top20_exploratory.csv`, `latest_cafe_branch_rank_comparison.csv`: 최신 카페 면적 보정 초안과의 동일 모집단 비교. 지도에는 두 탐색 순위를 별도 속성으로 기록.
- `.../oct06_integration/kakao_vs_osm_nearest_area_340.csv`, `integration_qa.csv`: 원천 간 비교와 QA.

재현: `python -m scripts.extract_maximus_osm_walk_graph --pbf <2026-10-02_PBF> --out <임시_graph>`, `python -m scripts.build_hanbyeol_osm_walk_access --nodes <임시_graph>/nodes.csv --edges <임시_graph>/edges.csv`, `python -m scripts.build_hanbyeol_20261006_integration`. OSM 단계에는 `osmium`, `shapely`, `pyproj`, `networkx`, `pandas`가 필요하다. 스냅샷 팀 파일을 함께 제공하며, API 키나 검증되지 않은 S4 양성판정은 생성하지 않았다.
