# 공식 상권 POI 피처 반영 기록

## 원본

- 파일: `data/external/official_area_poi_features_20260916.csv`
- 제공 시점: 2026-09-17
- 관측 기준일: 2026-09-16
- 단위: 25% 접근성 기준 공식 상권 786개, 상권 코드(`area_code`)별 1행

## 2025년 기준 추천 피처

식사·카페·공부·쇼핑·여가문화의 기준 피처는 서울시 상권분석서비스 **점포-상권 2025년** 자료를 쓴다. 이 자료는 상권 코드가 있어 공식 상권 폴리곤의 `area_code`와 직접 결합하며, 결과는 `data/processed/polygon_purpose_mapping_2025/official_area_purpose_polygon_mapping_2025.csv`에 저장한다.

- 식사: 음식점·제과·주점 업종
- 카페: 커피-음료 업종
- 공부: 독서실·서적·문구·학원 업종
- 쇼핑: 의류·화장품·식품소매·생활소매 업종
- 여가문화: 오락·스포츠·숙박 업종

## 2026 POI 보조자료 반영 범위

이 자료는 `여가문화` 목적의 문화·전시·공연·영화·공원·스포츠시설 POI 피처다. 기존 2025년 PATH-v0와 `area_code`로 결합하되, 원본 순위는 덮어쓰지 않는다. 새 산출물은 `data/processed/leisure_poi_enrichment/official_area_leisure_poi_enriched_current.csv`다. 이 파일은 현재 스냅샷 참고용이며 2025년 기준 추천점수에는 반영하지 않는다.

## 제한

- `feature_snapshot_date`가 2026-09-16이고 `historical_2025_use_allowed=0`이므로 2025년 성능 검증 및 과거 매출 예측에는 사용 금지다.
- 원천의 `operation_verified_open_count`, `open_now`가 전부 비어 있으므로 운영 중 여부는 점수화하지 않는다.
- 식사·카페·공부·쇼핑 목적 POI는 포함하지 않는다. 이 목적들은 기존 업종·점포·매출 피처를 유지한다.

## 폰트 아카이브

`assets/fonts/D2Coding-Ver1.3.2-20180524/`에 원본 폰트 패키지를 보관한다. 제공 폴더에 별도 라이선스 파일이 없어, 외부 배포 전에는 공식 D2Coding 라이선스를 별도로 확인해야 한다.
