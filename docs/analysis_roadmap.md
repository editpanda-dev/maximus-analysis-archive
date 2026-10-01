# 데이터 분석 및 통계기법 로드맵

## 분석 원칙

- 통계모형은 관계와 불확실성 해석, ML은 예측과 랭킹 성능 개선에 사용한다.
- 최대 이동시간은 choice set을 제한하는 hard constraint이며, 후보 안에서는 이동시간을 비용 변수로 사용한다.
- 시간 순 분할과 관측 시점 기준 feature 생성으로 미래 정보 누수를 막는다.
- 집계 관측자료이므로 개인 수준 선택이나 인과효과로 표현하지 않는다.

## 0. Feasibility 및 schema audit

검증 항목:

- 파일별 기간, 행 수, 인코딩, dtype, grain, 논리 key
- 날짜·시간·연령·목적·업종·행정동 코드 정의
- 중복, 결측, 0, 마스킹, 이상치
- 250m 격자→행정동 point-in-polygon 매칭률
- JOIN 전후 행 수, key cardinality, 이동량·소비건수·금액 보존율
- many-to-many JOIN 및 지역코드 개편 여부

중단 기준: 공통 공간 단위 매칭률이나 핵심 측정값 보존율이 분석에 부적절하면 상권 단위 모델링을 미루고 행정동 단위로 축소한다.

## 1. 분석 데이터마트

1차 grain:

```text
date × hour × origin_dong × destination_dong × age_group × purpose
```

핵심 outcome:

- `mobility_inflow`: 목적지 유입량
- `card_spend_count`: 카드 이용건수
- `card_spend_amount`: 카드 이용금액
- `outside_consumer_ratio`: 외부 소비 비중
- `destination_share`: 동일 출발·조건 내 목적지 점유율

핵심 exposure/feature:

- 이동비용: 평균 이동시간, 거리, 이동시간 spline
- 상권 구성: 음식·카페·소매·문화 밀도, 점포 수, 프랜차이즈 비율
- 다양성: Shannon entropy, HHI
- 규모·활력: 추정매출, 상주·직장·생활인구, 집객시설, 개폐업률
- 맥락: 연령, 평일/주말, 시간대, 목적, 계절

## 2. EDA 및 집단 차이

| 질문 | 분석 | 보고 항목 |
|---|---|---|
| 목적별 이동비용 차이 | Welch ANOVA 또는 Kruskal-Wallis | 효과크기, 95% CI, 사후검정 |
| 연령·시간대별 목적지 차이 | 교차표, 카이제곱, 표준화 잔차 | Cramer's V, FDR 보정 |
| 상권 특성과 유입 관계 | 산점도, spline smoother, 상관 | Pearson/Spearman, 비선형성 |
| 이동과 소비의 결합 | OD·목적지 집계 비교 | 시차별 상관, 분포와 이상치 |

반복 검정은 Benjamini-Hochberg FDR로 보정하고, 큰 표본에서 p-value만 과대해석하지 않도록 효과크기와 bootstrap CI를 함께 제시한다.

## 3. 연구질문별 추론모형

### RQ1. 이동비용과 유입

```text
mobility_inflow ~ travel_time + spline(travel_time)
                  + origin/date/hour fixed effects
                  + destination controls
```

- Poisson을 기준선으로 적합
- 과산포가 확인되면 Negative Binomial을 주 모형으로 사용
- 0이 과도하면 zero-inflated/hurdle은 진단 후 보조 분석으로만 검토
- 목적지·자치구 단위 군집 강건 표준오차 적용

### RQ2. 이동시간 통제 후 상권 매력

```text
mobility_inflow ~ travel_time + category_diversity
                  + restaurant_density + cafe_density
                  + franchise_ratio + attraction_facilities
                  + sales/population controls + fixed effects
```

- 연속변수 표준화 후 계수 크기 비교
- VIF와 상관행렬로 다중공선성 진단
- 상권 규모 변수의 log 변환 및 대안 사양 비교
- 결과는 발생률비(IRR)와 평균 한계효과로 제시

### RQ3. 조건별 이질성

사전 지정 상호작용:

- `cafe_density × weekend`
- `category_diversity × age_group`
- `restaurant_density × dinner_time`
- `travel_time × purpose`

상호작용의 p-value만 제시하지 않고 조건별 예측값과 한계효과 그래프를 보고한다. 목적지·자치구 random intercept 혼합효과모형과 고정효과모형을 비교한다.

### RQ4. 이동과 실제 소비

- 카드 이용건수: Negative Binomial
- 카드 이용금액: log-선형, Gamma GLM, Tweedie 중 잔차·예측 성능으로 선택
- 외부 소비 비율: fractional logit 또는 0·1 값이 적다면 beta regression
- 동일 시점 상관과 1개 시점 시차 모형을 구분해 역방향 해석 위험 점검

## 4. 목적지 선택모형

선택 strata별로 최대 이동시간 이내 모든 후보 목적지를 생성한다.

```text
stratum = date × hour × origin × age_group × purpose
row = stratum × candidate_destination
```

- 기준선: 이동시간 최단순, 전체 인기순, 동일조건 과거 유입순
- 주 모형: Conditional Logit
- 확장: 선호 이질성 자료가 충분할 때 Mixed Logit
- 집계자료에서는 개인 choice event라고 표현하지 않고 strata 내 목적지 점유/count로 해석

## 5. 공간 분석

1. 목적지별 모형 잔차를 지도화한다.
2. Global Moran's I로 공간 자기상관을 검정한다.
3. 유의한 경우 Local Moran's I 또는 Getis-Ord Gi*로 hotspot을 탐색한다.
4. 잔차 공간의존성이 지속될 때만 Spatial Lag/Error 모형을 비교한다.

Hidden Destination은 `actual inflow - expected inflow` 잔차가 반복적으로 큰 양수인 목적지로 정의하고, 단일 시점 이상치를 후보로 확정하지 않는다.

## 6. Attraction Score

임의 가중치는 사용하지 않는다.

1. 후보 지표 방향 통일 및 z-score 표준화
2. KMO, Bartlett 검정과 상관구조 확인
3. PCA 또는 요인분석의 component 수 결정
4. loading과 설명분산 보고
5. 기간·표본 변경 시 순위 안정성 검증

구성 타당성이 약하면 하나의 종합점수 대신 개별 지표 대시보드로 남긴다.

## 7. 예측 및 랭킹

- 해석 기준선: Logistic/Multinomial Logistic
- ML 후보: LightGBM, CatBoost
- 검증: train→validation→test 시간 순 분할과 rolling-origin validation
- 일반화 확인: 미관측 출발지 또는 목적지 holdout을 보조 검증으로 사용
- 설명: SHAP, permutation importance, 조건별 한계효과

평가:

- Ranking: Recall@5, NDCG@5, MRR
- Utility: 이동시간 증가량, baseline 대비 목적 적합도 개선
- System: Coverage, 목적지 다양성
- 불확실성: strata 단위 paired bootstrap 95% CI

성공 여부는 baseline보다 수치가 단순히 높은지가 아니라, bootstrap CI 기준으로 개선이 일관되는지와 특정 출발지·시간대에만 성능이 집중되지 않는지를 함께 판단한다.

## 8. 강건성 및 실패 해석

- 최대 이동시간 30/45/60분 choice set 민감도
- 행정동·상권 공간 단위 변경
- 최소 유입량 threshold 변경
- 평일/주말, 연령, 목적별 하위표본 반복
- 코로나·특수기간 및 극단값 제외
- 원점수·log 변환·winsorization 비교

유의한 상권 특성이 없으면 실패로 숨기지 않고, 이동비용과 목적지 고정효과가 대부분을 설명했는지 또는 공간 단위·측정오차 때문에 추가 설명력이 제한되었는지를 결과로 보고한다.
