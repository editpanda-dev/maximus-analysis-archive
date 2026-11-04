# 여가문화 목적 점수 v1

기준일: 2026-09-30  
담당: 지우진  
대상: 동대문구 334개 출발지에서 세 시간대 공통 접근률 25% 이상인 공식 상권 786개

## 이 산출물의 역할

이 파일은 여가문화를 단일 업종 규모가 아니라 `문화·시설`, `야간 활동`, `상권 크기`를 분리해 보는 현재 추천 기준선이다. 최종 개인화 모델이나 과거 성능 검증 결과가 아니다.

2025년 상권 점포·매출 자료와 2026-09-16 POI 스냅샷의 시점이 다르므로, 두 자료를 결합한 `current_exploration_score_raw` 및 `leisure_size_adjusted_score`는 **현재 후보 설명·탐색용**으로만 쓴다. 2025년 예측 정확도를 주장하는 데 사용하지 않는다.

## 분류와 입력

| 신호 | 원천 | 포함 기준 | 역할 |
|---|---|---|---|
| 기존 여가 맥락 | 서울시 상권분석서비스 2025 점포·추정매출 | 영화·오락·스포츠·숙박 등 기존 여가문화 분류 | `path_v0_score` |
| 야간 여가 | 서울시 상권분석서비스 2025 점포·추정매출 | `호프-간이주점` | 저녁·심야 공급 및 소비 신호 |
| 문화·시설 | 2026-09-16 POI 스냅샷 | 박물관, 전시, 공연, 영화, 문화센터, 공원, 스포츠시설 | 현재 설명 신호 |
| 요리주점·호프 POI | 카카오 로컬 2026-09-30 키워드 스냅샷 | 카카오 분류 `음식점 > 술집 > 호프,요리주점` | 현재 야간 식사·여가 보조 신호 |
| 유흥주점 POI | 카카오 로컬 2026-09-30 키워드 스냅샷 | 카카오 분류 `가정,생활 > 유흥시설 > 유흥주점` | 성인 전용 태그; 일반 추천 점수 미반영 |

`호프-간이주점`은 식사 해석에서 빼고 야간 여가에 추가했다. 원천 100대 업종에는 `요리주점`, `유흥주점`이라는 별도 코드가 없으므로 2025년 매출·점포 시계열에는 임의로 대입하지 않는다. 최신 현황은 아래 카카오 POI 보조 신호로만 보강한다.

2026-09-30 카카오 스냅샷에서는 중복 제거 후 1,229개 POI를 수집했다. 4×4 기본 타일 32개 검색에서 3페이지·45개 상한에 걸린 타일은 0개였으며, 수집 감사 파일에 이 결과를 남겼다. 향후 상한이 감지되면 해당 타일을 최대 2단계까지 4분할해 다시 검색한다.

공식 상권 내부에는 `호프,요리주점` 387개와 유흥주점 352개가 있었다. 경계 밖 POI 중 직선거리 400m 이내인 167개만 카카오 최단 보행경로로 재검증했고, 148개가 실제 도보 400m 이내였다. 최종 도보권 개수는 `호프,요리주점` 465개, 유흥주점 422개다. 유흥주점 수는 `adult_nightlife_walk400_count`로만 보존하며, `adult_nightlife_recommendation_eligible=False`를 고정한다.

## 점수 구조

```text
nightlife_2025_score
  = 0.60 × 호프-간이주점 점포수 백분위
  + 0.40 × (17~21시 + 21~24시) 매출비중 백분위

historical_leisure_context_score
  = 0.70 × 기존 2025 PATH-v0 여가 점수
  + 0.30 × nightlife_2025_score

current_poi_explanation_score
  = 0.55 × 상권 내부 문화 POI 밀도 백분위
  + 0.25 × 상권 내부 문화 POI 유형 다양성 백분위
  + 0.20 × 상권 내부 또는 경계 도보 400m 내 호프·요리주점 POI 밀도 백분위

current_exploration_score_raw
  = 0.70 × historical_leisure_context_score
  + 0.30 × current_poi_explanation_score
```

현재 요리주점 신호를 넣기 전·후의 크기 보정 전 Top 10은 8개가 겹쳤다. 즉 새 신호가 순위를 전면 교체하지는 않지만 일부 후보의 순서를 실제로 바꾸며, 영향 정도는 `leisure_culture_v1_audit.json`에서 계속 감사한다.

문화 POI는 기존처럼 상권 내부만 점수화한다. 이번에 보강한 야간 POI는 상권 내부 또는 경계에서 실제 보행거리 400m 이내인 경우만 합산한다. 직선거리 400m 초과 POI는 도보거리도 400m 이하가 될 수 없으므로 API를 호출하지 않고 제외했다. 경계 밖 POI의 출발점은 상권 경계상 최단점이라는 대리점이므로 실제 출입구 기반 경로와는 차이가 날 수 있다.

## 크기 쏠림 보정과 제외

`leisure_size_adjusted_score`는 원점수에서 `log(상권 면적)`과 `log(전체 점포 수)`로 설명되는 부분을 제거한 잔차의 백분위다. 이는 “작은 상권이 무조건 낫다”는 뜻이 아니라, 큰 상권의 단순 규모 우위를 줄인 비교용 순위다.

관광특구 6개는 786개 분석 우주에는 유지하지만 `recommendation_eligible=False`로 처리해 일반 이용자에게 하나의 너무 넓은 권역을 추천하는 것을 막는다.

## 산출물

- `data/processed/leisure_culture_v1/official_area_leisure_culture_v1_786.csv`: 786개 전체 피처·점수·제외 사유
- `data/processed/leisure_culture_v1/leisure_culture_v1_raw_top10.csv`: 크기 보정 전 현재 탐색 Top 10
- `data/processed/leisure_culture_v1/leisure_culture_v1_size_adjusted_top10.csv`: 크기 보정 후 추천 가능 Top 10
- `data/processed/leisure_culture_v1/leisure_culture_v1_audit.json`: 행 수·관광특구 수·크기 상관 감사
- `data/external/kakao_nightlife_pois_20260930.csv`: 키워드·카테고리·좌표·카카오 place ID가 보존된 최신 POI 원천
- `data/external/kakao_nightlife_pois_20260930_collection_audit.json`: 검색 타일·상한 미해결 여부 감사
- `data/processed/nightlife_poi_v1/nightlife_poi_walk400_detail.csv`: POI별 내부 여부·직선거리·카카오 보행거리·판정
- `data/processed/nightlife_poi_v1/official_area_nightlife_poi_features_786.csv`: 상권별 도보 400m 호프·요리주점/유흥주점 개수

## 재현

```bash
python3 scripts/collect_kakao_nightlife_pois.py --output data/external/kakao_nightlife_pois_20260930.csv
python3 scripts/build_nightlife_poi_scope.py --places data/external/kakao_nightlife_pois_20260930.csv
python3 scripts/enrich_nightlife_walk_access.py
python3 scripts/build_leisure_culture_v1.py
python3 -m pytest -q
```

## 다음 보강 대상

1. 사용자 출발지·출발 시각별 실제 30분 도달 후보만 다시 필터링
2. 카카오 키워드 검색의 정기 스냅샷과 폐업·업종 변경 검증
