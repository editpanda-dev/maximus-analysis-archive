# 장한별 2주차 공공 학습시설 POI 업무 점검

기준일: 2026-09-21  
기준 업무: `docs/team_week2_workplan.md`의 “장한별 — 공공 학습시설 POI”

## 1. 판정 기준

이 문서는 개인 평가가 아니라, 2주차에 배정한 산출물이 재현 가능하고 다음 통합 단계에서 바로 사용 가능한지를 점검하기 위한 인수인계 기록이다. 제출 엑셀과 Git에 추적된 CSV·스크립트·문서를 함께 확인했다.

## 2. 업무별 점검 결과

| 배정 업무 | 배정 시 기대 산출물 | 실제 확인 파일 | 상태 | 확인 결과 |
|---|---|---|---|---|
| 원천 데이터 조사 | 원천별 출처·기준일·라이선스·좌표 제공 여부 | `data/external/study_public_facility_poi.csv`, `docs/study_poi_source_and_taxonomy.md` | 부분 완료 | 출처명·출처 URL·기준일·좌표는 있다. 원천별 라이선스와 이용 조건은 문서에 없다. |
| 표준 스키마 정리 | 시설명·주소·위도·경도·운영상태·시설유형 표준화 | `data/external/study_public_facility_poi.csv` | 완료 | 268행·36열이다. 시설명·유형·좌표·운영상태·출처·분류 규칙을 보존한다. 주소는 46건 비어 있다. |
| 중복 제거 | 중복 제거 기준과 전후 건수 | `data/external/study_public_facility_poi.csv` | 부분 완료 | 최종 `place_id` 268개는 모두 고유하다. 다만 원천별 최초 건수, 제거 건수, 이름·주소·좌표 중복 판정 규칙은 기록되지 않았다. |
| 시설 유형 분류 | 도서관·열람실·청년공간·대학시설 분류 | 원천 CSV, `docs/study_poi_source_and_taxonomy.md` | 완료 | 공공도서관 205개, 열람실 14개, 청년공간 17개, 대학 학습시설 9개, 스터디카페 10개, 대형카페 13개로 분류했다. |
| 카페 중복 방지 | 카카오 POI와 공공시설 점수의 분리 | 원천 CSV의 `aggregation_eligible`, 분류 문서 | 완료 | 스터디카페·대형카페 23개는 원천 상세정보에는 남기되 공공시설 점수에서는 제외했다. |
| 786개 상권 공간 결합 | 상권 내부·400m 이내·인접 전용 시설 수 | `scripts/build_study_public_facility_features.py`, `data/processed/study_public_facility_features.csv` | 완료 | 786행·20열이며 `area_code`는 786개 모두 고유하다. 상권 내부·400m 범위·인접 전용 수치를 분리한다. |
| 대학시설 공개 접근 검증 | 외부 이용 가능한 대학시설만 점수 반영 | 원천 CSV의 `public_access_verified` | 미완료, 안전 처리 완료 | 대학 학습시설 9개 모두 공개 접근 미확인이다. 원천에는 보존하고, 현재 추천 점수에서는 제외했다. |
| 공부 top 20 수동 점검 | 지도 이미지·점검표·예외 사례 기록 | 해당 Git 산출물 없음 | 미완료 | 목적별 top 20 파일은 있으나, 시설 좌표를 지도에서 수동 점검한 증빙 파일은 없다. |
| 한계 문서화 | 2026 POI를 2025 검증에 사용하지 않는다는 명시 | `docs/study_poi_source_and_taxonomy.md`, `data/processed/study_stay_poi_enrichment/README.md` | 완료 | 현재 추천용 보조 피처이며 2025년 매출 예측·성능 검증에는 사용하지 않는다고 명시했다. |

## 3. 현재 Git 정식 산출물

```text
data/external/study_public_facility_poi.csv
data/processed/study_public_facility_features.csv
scripts/build_study_public_facility_features.py
docs/study_poi_source_and_taxonomy.md
tests/test_build_study_public_facility_features.py
```

검토용 엑셀 `마아악시무쓰 (1).xlsx`는 Summary, Area Features, POI Detail, QA, Sources, Methodology의 6개 시트로 정리돼 있다. 다만 이 파일 자체는 현재 Git 정식 산출물로 보관되지 않았다.

## 4. 후속 완료 기준

아래 세 산출물을 추가하면 장한별의 2주차 범위는 완결된다.

```text
docs/study_poi_license_and_deduplication.md
data/processed/study_public_facility_top20_manual_check.csv
docs/study_public_facility_top20_manual_check.md
```

첫 문서에는 원천별 라이선스, 수집일, 최초 건수, 중복 제거 후 건수, 중복 제거 키를 기록한다. 수동 점검 CSV에는 공부 top 20 상권별 시설명, 좌표, 상권 내부 또는 400m 이내 여부, 운영·공개 접근 확인 결과, 예외 사유를 기록한다. Markdown 문서에는 점검 기준과 주요 예외 사례를 요약한다.
