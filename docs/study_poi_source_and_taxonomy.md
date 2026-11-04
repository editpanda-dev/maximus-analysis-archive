# 공공 학습시설 POI: 출처와 분류 기준

## 범위

이 데이터는 동대문구 출발, 세 시간대 모두 대중교통 30분 이내 접근률 25% 이상인 공식 상권 786개에 결합하는 공공·교육형 학습시설 보강 데이터다. 기존 카카오 기반 스터디카페·스타벅스 스냅샷과 중복 집계하지 않기 위해, 이 산출물의 **점수 대상**은 공개 접근이 확인된 공공도서관·열람실·청년공간으로 한정한다.

## 원천 스냅샷

`data/external/study_public_facility_poi.csv`는 2026-09-21에 확인한 시설 POI 268개 스냅샷이다. 각 행은 시설명, 좌표, 운영상태, 공개 접근 확인 여부, 학습 적합성 근거, 출처 URL을 보존한다.

| 시설 유형 | 원천 수 | 권장 점수 반영 |
|---|---:|---|
| public_library | 205 | 반영 |
| reading_room | 14 | 반영 |
| youth_space | 17 | 반영 |
| university_learning_facility | 9 | 원천에는 보존, 공개 접근 미확인으로 점수 제외 |
| study_cafe | 10 | 이 파일에서는 제외; 카카오 스냅샷과 통합 단계에서 처리 |
| large_cafe | 13 | 이 파일에서는 제외; 카카오 스냅샷과 통합 단계에서 처리 |

## 공간 결합과 점수 범위

`scripts/build_study_public_facility_features.py`는 WGS84 좌표를 EPSG:5186으로 변환한 뒤, 공식 상권 폴리곤 내부와 경계 400m 이내를 각각 계산한다. 산출물은 `data/processed/study_public_facility_features.csv`이며 `area_code`로 기존 786개 상권 피처와 결합한다.

- `study_public_*`: 공개 접근이 확인된 공공도서관·열람실·청년공간 **236개**만 집계한 생산 점수용 피처다.
- `study_public_all_*`: 대학 학습시설 후보 9개까지 더한 **245개**의 검토용 전체 후보 피처다. 추천 점수에는 쓰지 않는다.
- `poi_<type>_inside_count`, `poi_<type>_buffer400_count`: 유형별 전체 후보 수로, 대학시설을 안전하게 제외했는지 검토할 수 있도록 보존한다.

대학 학습시설은 원천에 유지하지만 `public_access_verified=1`이 확인될 때까지 점수 집계에서 제외한다.

## 해석 주의

대학 시설과 일부 독서실은 공개 접근 또는 이용 조건이 제한될 수 있다. 따라서 `public_access_verified`, `study_access_verified`, `mandatory_purchase`를 보존하고, 추천 화면에서는 공개형·이용조건 확인형을 구분한다. 이 데이터는 2026년 공간 스냅샷이므로 2025년 매출 예측 성능 검증에는 사용하지 않는다.

원천별 이용 조건과 중복 제거 방식은 [study_poi_license_and_deduplication.md](study_poi_license_and_deduplication.md), 상위 20개 상권의 지도 수동 점검은 [study_public_facility_top20_manual_check.md](study_public_facility_top20_manual_check.md)에 기록한다.
