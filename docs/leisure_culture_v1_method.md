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

`호프-간이주점`은 식사 해석에서 빼고 야간 여가에 추가했다. 원천 100대 업종에는 `요리주점`, `유흥주점`이라는 별도 코드가 없으므로, 이 둘은 0으로 추정하거나 임의로 대입하지 않는다. 별도 POI 원천을 확보한 뒤 보강 대상이다.

## 점수 구조

```text
nightlife_2025_score
  = 0.60 × 호프-간이주점 점포수 백분위
  + 0.40 × (17~21시 + 21~24시) 매출비중 백분위

historical_leisure_context_score
  = 0.70 × 기존 2025 PATH-v0 여가 점수
  + 0.30 × nightlife_2025_score

current_poi_explanation_score
  = 0.70 × 상권 내부 문화 POI 밀도 백분위
  + 0.30 × 상권 내부 문화 POI 유형 다양성 백분위

current_exploration_score_raw
  = 0.70 × historical_leisure_context_score
  + 0.30 × current_poi_explanation_score
```

400m 밖 인접 POI는 `poi_nearby_only_count`로 남겨 설명에 활용하지만, 내부 시설 밀도 점수에 합산하지 않는다. 따라서 큰 폴리곤이 단지 반경 안의 주변 시설을 많이 끌어안아 유리해지는 문제를 줄인다.

## 크기 쏠림 보정과 제외

`leisure_size_adjusted_score`는 원점수에서 `log(상권 면적)`과 `log(전체 점포 수)`로 설명되는 부분을 제거한 잔차의 백분위다. 이는 “작은 상권이 무조건 낫다”는 뜻이 아니라, 큰 상권의 단순 규모 우위를 줄인 비교용 순위다.

관광특구 6개는 786개 분석 우주에는 유지하지만 `recommendation_eligible=False`로 처리해 일반 이용자에게 하나의 너무 넓은 권역을 추천하는 것을 막는다.

## 산출물

- `data/processed/leisure_culture_v1/official_area_leisure_culture_v1_786.csv`: 786개 전체 피처·점수·제외 사유
- `data/processed/leisure_culture_v1/leisure_culture_v1_raw_top10.csv`: 크기 보정 전 현재 탐색 Top 10
- `data/processed/leisure_culture_v1/leisure_culture_v1_size_adjusted_top10.csv`: 크기 보정 후 추천 가능 Top 10
- `data/processed/leisure_culture_v1/leisure_culture_v1_audit.json`: 행 수·관광특구 수·크기 상관 감사

## 재현

```bash
python3 scripts/build_leisure_culture_v1.py
python3 -m pytest tests/test_build_leisure_culture_v1.py -q
```

## 다음 보강 대상

1. 요리주점·유흥주점 별도 POI 원천 확보 및 공간 결합
2. POI의 400m 직선거리 대신 카카오 보행 경로 기반 접근성 결합
3. 사용자 출발지·출발 시각별 실제 30분 도달 후보만 다시 필터링
