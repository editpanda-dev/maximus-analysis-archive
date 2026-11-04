# 카페·공부 4~7단계 실행 결과와 10월 6일 인계

실행일: 2026-10-03. 기준: 786개 공식 상권 `area_code`, 서울시 2025Q4 점포·매출, 2026년 9월 공공·카카오 POI. 재현 명령: `python -m scripts.build_hanbyeol_oct06_steps_4_7`. 김건우님 식사 taxonomy의 제과점·호프 업종 귀속은 [교차 검수표](hanbyeol_steps_1_3_review_20261003.md)를 따른다. **결과는 완성된 v1 추천점수가 아니라 검증 가능한 부분의 초안**이다.

## 4. 보행거리와 인접시설

`scripts/build_hanbyeol_walk_access.py`는 실제 보행 가능 노드·링크(`node_id,x,y` 및 `u,v,geometry_wkt,length_m,oneway_walk`)를 EPSG:5186으로 받도록 준비되어 있다. 저장소와 현재 실행 환경에는 법적으로 보행 가능한 경로 그래프·시설 출입구 연결 자료가 없다. 이 실행 환경에서는 `networkx`, `pyproj`, `shapely`, `geopandas`도 불러올 수 없다. 따라서 **실제 보행거리 계산 0건**이며 `walk_distance_m`이나 `walk_access_400/500/600`에 직선거리 값을 대입하지 않았다. `walk_radius_400_500_600_status.csv`의 세 행은 수치 없이 `blocked_missing_pedestrian_network`다.

원천 확보 후보는 [Geofabrik 대한민국 OSM 추출본](https://download.geofabrik.de/asia/south-korea.html)이다. 실제 사용 전 보행 금지 도로, 지하/고가 연결, 일방통행 보행, 상권 경계 진입점, 시설 출입구·스냅 간격, 원천 기준일을 검수해야 한다. OSM 파일 존재 자체가 서울의 모든 보행경로·출입구를 증명하지 않는다. 김건우님 자료의 도보권 집계도 본문에서 직선거리 400m로 명시되어 있으므로 현재 상권 간 비교에서 보행거리로 치환하지 않는다.

기존 공공 POI의 **직선거리(`euclidean_legacy`)** 인접 가중치 0 / 0.25 / 0.5 Top 10을 같은 상권에서 비교하면 0.25 대비 공통률은 60% / 100% / 80%다. 이 수치는 기존 236 플래그의 공공시설 성분에만 적용되며, 공부 전체 점수의 보행거리 민감도가 아니다. 0.25의 최종 채택 근거로 간주하지 않는다.

## 5. 크기 보정과 점수 상태

기존 카페 공급의 4가지 독립 지표(절대 점포 수, 면적당 밀도, 업종 특화도, 면적·전체 점포수를 설명한 잔차)를 786개에 대조했다. 지표 단독 면적 순위상관은 각각 **0.753 / 0.183 / 0.194 / -0.005**다. 상권 규모로 인한 쏠림과 반대 방향 쏠림을 함께 점검해야 하므로 잔차를 즉시 확정식으로 선택하지 않았다.

잔차를 공급 70%, 기존 관측 소비 부분을 30%로 놓은 **진단용 점수**도 만들었다. 점포 10개·전체 점포 50개 이상이며 카페 매출이 둘 다 공개된 추천 가능 상권 **178개**를 동일 모집단으로 비교하면 기존 카페점수의 면적 상관은 **-0.155**, 잔차 대안은 **-0.227**, Top 10 공통률은 **60%**다. 카페 점수에 잔차만 끼워 넣으면 작은 상권 쪽으로 더 치우칠 수 있어 채택을 보류한다. 잔차 진단값은 786행 중 자격 있고 매출 완전관측인 184행에만 기록했고 관광특구 6개는 위의 178행 순위에서 제외했다. 기존 밀도 분모의 0.02km² 하한도 아직 가정이다.

`cafe_study_v1_handoff_786.csv`의 카페 점수 상태는 `complete` **224**, `supply_only` **232**, `insufficient` **330**개다. `cafe_full_score`는 complete에만, `cafe_supply_only_score`는 supply_only에만 숫자를 기록한다. 매출 미공개·부분 공개를 관측 0으로 만들지 않는다. 공부의 `study_final_score`, 미검증 `verified_s4_count` 및 보행 상태는 전부 NA/미산출이다. 기존 `study_legacy_proxy_score`는 별도의 탐색 열이며 S3a+S3b를 검증된 고유 시설로 해석하지 않는다.

## 6. 순위·설명·지도

| 산출물 | 상태와 해석 |
| --- | --- |
| 카페 Top 10·20 | 매출 양 업종 완전관측, 관광특구 제외 집단의 탐색 순위. 점포·매출 근거 문장 및 C1/C2 하위점수 분해 포함 |
| 공부 Top 10·20 | **기존 체류 프록시** 순위만 별도로 표기. S4·보행 및 공개 학습시설의 엄격 판정 미반영 |
| 카페+공부 Top 10·20 | 위 카페 관측 집단에서 두 목적의 백분위를 재계산한 **탐색** 조합. 공부 v1 순위가 아님 |
| 식사+카페+공부 Top 10 | `not_computed`. 김건우님 식사 점수와 카페의 제과점 이관이 같은 버전으로 통합되고, 공부 최종 점수가 나온 뒤 계산 |
| 786개 GeoJSON | 위 탐색 순위 속성을 원본 상권 폴리곤에 표시. `map_status=preview_no_verified_walk_or_study_score` |

카페 하위분류는 C1·C2 두 점수만 있고 C_stay는 검증 0건이라 `cafe_top3_status=only_C1_C2_scored_C_stay_unverified`다. 공부 최고 하위분류·Top 3은 확정할 수 없다. 점수 상위권의 차이를 만족도 격차로 해석하지 않는다. 관광특구 6개는 지도와 786행 원본에 보존하고 탐색 순위에서만 제외했다.

## 7. 자체 QA와 남은 입력

`oct06_steps_4_7_qa.csv`는 **PASS 11건**, `BLOCKED_INPUT` 1건, `BLOCKED_EVIDENCE` 1건, `BLOCKED_INTEGRATION` 1건이다. 확인 대상은 786행·코드 고유, 원본 후보와 키 일치, 카페 완전관측 점수 224행, 공급 전용 232행, 점수 0~100, 공부 최종점수 NA, S4 확인 0, 관광특구 6개 순위 제외, Top 20 완전관측, 지도 786개 폴리곤이다. `cross_purpose_transfer_area_audit_786.csv`의 제과점·호프 이동량도 [앞 단계 검수](hanbyeol_steps_1_3_review_20261003.md)에서 확인했다.

남은 필수 입력은 (1) 권리·출처·기준일을 확인한 보행 네트워크와 시설 출입구, (2) 좌석·장시간/노트북/학습 이용의 개별 근거 및 검토자, (3) 김건우님 식사 v1과 팀 공통 분류의 동일 버전 점수다. 세 입력을 확보하면 보행 400/500/600m 재집계, 인접 0/0.25/0.5 비교, S4 및 엄격 공공시설 점수, 조합 Top 10, 최종 지도·설명을 다시 산출해야 한다.

결과 파일은 `data/processed/cafe_study_taxonomy/oct06_steps_4_7/`에 있다. 특히 `cafe_study_v1_handoff_786.csv`, `cafe_top20_observed_preview.csv`, `study_top20_legacy_proxy_preview.csv`, `cafe_study_top20_exploratory.csv`, `cafe_study_preview_map_786.geojson`, `cafe_size_four_methods_comparison.csv`, `cafe_residual_score_variant_comparison.csv`, `public_adjacency_euclidean_legacy_only.csv`, `walk_radius_400_500_600_status.csv`, `oct06_steps_4_7_qa.csv`를 함께 전달한다.
