# 장한별 2주차 공공 학습시설 POI 업무 점검

기준일: 2026-09-21  
기준 업무: `docs/team_week2_workplan.md`의 “장한별 — 공공 학습시설 POI”

## 1. 판정 기준

이 문서는 개인 평가가 아니라, 2주차에 배정한 산출물이 재현 가능하고 다음 통합 단계에서 바로 사용 가능한지를 점검하기 위한 인수인계 기록이다. 제출 엑셀과 Git에 추적된 CSV·스크립트·문서를 함께 확인했다.

## 2. 업무별 점검 결과

| 배정 업무 | 배정 시 기대 산출물 | 실제 확인 파일 | 상태 | 확인 결과 |
|---|---|---|---|---|
| 원천 데이터 조사 | 원천별 출처·기준일·라이선스·좌표 제공 여부 | `data/external/study_public_facility_poi.csv`, `docs/study_poi_license_and_deduplication.md` | 완료 | 출처명·URL·기준일·좌표와 원천별 재이용 주의사항을 기록했다. 배포 직전 원천의 최신 이용 조건을 재확인해야 한다. |
| 표준 스키마 정리 | 시설명·주소·위도·경도·운영상태·시설유형 표준화 | `data/external/study_public_facility_poi.csv` | 완료 | 268행·41열이다. 시설명·유형·좌표·운영상태·출처·분류·공간결합·점수반영·수동검토 필드를 보존한다. 주소 누락 46건은 상태값으로 남겼다. |
| 중복 제거 | 중복 제거 기준과 전후 건수 | `data/external/study_public_facility_poi.csv`, `docs/study_poi_license_and_deduplication.md` | 완료 | 최종 `place_id` 268개가 모두 고유하며, 상권별 집계도 `place_id` 고유값으로 한다. 원천 최초 수집 단계의 제거 전 원시 덤프는 보관되지 않아 그 수준의 제거 건수는 소급 확인할 수 없다. |
| 시설 유형 분류 | 도서관·열람실·청년공간·대학시설 분류 | 원천 CSV, `docs/study_poi_source_and_taxonomy.md` | 완료 | 공공도서관 205개, 열람실 14개, 청년공간 17개, 대학 학습시설 9개, 스터디카페 10개, 대형카페 13개로 분류했다. |
| 카페 중복 방지 | 카카오 POI와 공공시설 점수의 분리 | 원천 CSV의 `aggregation_eligible`, 분류 문서 | 완료 | 스터디카페·대형카페 23개는 원천 상세정보에는 남기되 공공시설 점수에서는 제외했다. |
| 786개 상권 공간 결합 | 상권 내부·400m 이내·인접 전용 시설 수 | `scripts/build_study_public_facility_features.py`, `data/processed/study_public_facility_features.csv` | 완료 | 786행·24열이며 `area_code`는 786개 모두 고유하다. 점수용 236개와 대학 후보까지 포함한 검토용 245개를 분리하고, 내부·400m·인접 전용 수치를 분리한다. |
| 대학시설 공개 접근 검증 | 외부 이용 가능한 대학시설만 점수 반영 | 원천 CSV의 `public_access_verified` | 미완료, 안전 처리 완료 | 대학 학습시설 9개 모두 공개 접근 미확인이다. 원천에는 보존하고, 현재 추천 점수에서는 제외했다. |
| 공부 top 20 수동 점검 | 지도 이미지·점검표·예외 사례 기록 | `data/processed/study_public_facility_top20_manual_check.csv`, `docs/study_public_facility_top20_manual_check.md` | 완료 | 20개 상권·117개 상권-시설 연결을 점검했다. 내부 18건, 400m 인접 99건이며 최대 거리는 393.5m다. |
| 한계 문서화 | 2026 POI를 2025 검증에 사용하지 않는다는 명시 | `docs/study_poi_source_and_taxonomy.md`, `data/processed/study_stay_poi_enrichment/README.md` | 완료 | 현재 추천용 보조 피처이며 2025년 매출 예측·성능 검증에는 사용하지 않는다고 명시했다. |

## 3. 현재 Git 정식 산출물

```text
data/external/study_public_facility_poi.csv
data/processed/study_public_facility_features.csv
data/processed/study_public_facility_top20_manual_check.csv
scripts/build_study_public_facility_features.py
docs/study_poi_source_and_taxonomy.md
docs/study_poi_license_and_deduplication.md
docs/study_public_facility_top20_manual_check.md
tests/test_build_study_public_facility_features.py
```

검토용 엑셀 `마아악시무쓰 (1).xlsx`는 Summary, Area Features, POI Detail, QA, Sources, Methodology의 6개 시트로 정리돼 있다. 다만 이 파일 자체는 현재 Git 정식 산출물로 보관되지 않았다.

## 4. 후속 완료 기준

## 4. 남은 운영상 확인 사항

Git 산출물 기준 2주차 범위는 완결됐다. 다만 외부 공개나 서비스 반영 전에는 다음을 다시 확인한다.

- 원천 제공기관의 최신 이용 조건 및 OSM 출처표시 의무
- 주소가 누락된 46개 POI의 주소 보완 필요성
- 대학 학습시설 9개의 실제 외부인 이용 가능 여부
- 실제 운영 시간·휴관·좌석 여유처럼 스냅샷만으로 보장할 수 없는 상태
