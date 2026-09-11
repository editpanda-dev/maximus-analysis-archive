# Colab 실행 순서

이 폴더의 노트북은 분석 목적별로 분리했다. 모든 노트북은 프로젝트 전체 폴더를 Google Drive에 올린 뒤, 첫 셀의 `PROJECT_DIR`만 실제 위치로 바꾸면 된다.

| 순서 | 노트북 | 목적 | 주요 산출물 |
|---|---|---|---|
| 01 | `01_transit_official_commercial_candidates_colab.ipynb` | 334개 출발지의 시간대별 30분 접근성, 행정동 탐색 생활권, 공식 상권 후보 생성 | `time_period_candidates.csv`, `commercial_area_candidates_25pct.csv` |
| 02 | `02_eda_and_path_baseline_colab.ipynb` | 유동인구–매출 괴리 EDA와 목적별 PATH-v0 기준선 생성 | `flow_sales_gap/`, `purpose_features/`, `purpose_rankings/` |
| 03 | `03_b078_spatial_mapping_colab.ipynb` | B078 250m OD 셀을 행정동으로 매핑하는 템플릿 | `b078_dong_mart/` |

## 실행 원칙

1. 01은 다른 노트북보다 먼저 실행한다. `02`의 접근성 후보 필터가 01의 결과를 읽는다.
2. B078 전체 원본은 빅데이터캠퍼스 반출·이용 정책을 따른다. 03은 공개 표본으로 스키마와 공간 매핑을 검증하는 용도이며, 표본 결과를 실제 추천 성능으로 해석하지 않는다.
3. API 키, `.env`, ODsay 원응답 캐시는 Drive·GitHub에 올리지 않는다.
4. 원본 CSV·ZIP은 `data/raw/`, 중간 네트워크 파일은 `data/interim/`, 분석 결과는 `data/processed/`에 둔다.

## 기존 노트북

`local_transit_30min_colab.ipynb`는 이전 교통 접근성 실행본이다. 새 작업에서는 01번 노트북을 기준본으로 사용한다.
