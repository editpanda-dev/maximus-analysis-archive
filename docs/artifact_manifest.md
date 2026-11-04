# 분석 산출물 매니페스트

이 문서는 막시무스 분석 저장소에서 참조하는 정식 파일 경로를 한곳에 고정한다. 스냅샷 데이터는 수집일을 파일명에 포함하고, 처리 결과는 공간 단위와 분석 범위를 파일명에 포함한다. `final`, `latest-final`, `v2-final` 같은 별칭은 사용하지 않는다.

| 분석 범위 | 원천 | 상권 피처 | 생성 스크립트 | 설명 문서 |
|---|---|---|---|---|
| 공부 체류: 카카오·공공 학습시설 보조 POI | `data/external/kakao_study_stay_pois_20260918.csv` + `data/external/study_public_facility_poi.csv` | `data/processed/study_stay_poi_enrichment/official_area_study_stay_enriched_current.csv` | `scripts/build_study_stay_poi_enrichment.py` | `data/processed/study_stay_poi_enrichment/README.md` |
| 공부 체류: 공공 학습시설 | `data/external/study_public_facility_poi.csv` | `data/processed/study_public_facility_features.csv` | `scripts/build_study_public_facility_features.py` | `docs/study_poi_source_and_taxonomy.md` |
| 목적별 기본 순위 | 서울시 상권·매출 원천 | `data/processed/commercial_area_purpose_features/official_area_purpose_latest_rankings.csv` | `scripts/build_commercial_area_purpose_features.py` | `data/processed/commercial_area_purpose_features/PURPOSE_RANKING_REPORT.md` |
| 생활이동 목적 피처 | `data/external/living_movement/` | `data/processed/living_movement/official_area_living_movement_features.csv` | `scripts/build_living_movement_features.py` | `docs/living_movement_data_dictionary.md` |
| 접근성 민감도 | 기존 도달성 결과 | `data/processed/accessibility_sensitivity/threshold_summary.csv` | `scripts/analyze_accessibility_sensitivity.py` | `docs/accessibility_threshold_validation.md` |

생활이동·접근성 민감도 항목은 예정 산출물이다. 나머지 세 범위는 현재 원격 브랜치에 있는 기준선 또는 병합 대기 산출물이다.
