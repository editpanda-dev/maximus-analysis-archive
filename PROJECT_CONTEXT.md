# DAT 8기 캡스톤 프로젝트 종합 정리
## Where Do We Go? — 수도권 생활이동·카드소비·상권 데이터를 활용한 소비 목적지 선택 요인 분석 및 추천 모델

작성일: 2026-08-08  
용도: Codex 전달용 프로젝트 컨텍스트 / 설계 문서  
상태: 브레인스토밍 및 주제 선정 단계

---

# 0. 프로젝트 한 줄 요약

**사용자가 갈 수 있는 여러 지역 중 왜 특정 상권이 실제로 선택되고 소비까지 발생하는지를 수도권 이동·카드소비·상권 데이터를 통해 통계적으로 분석하고, 그 결과를 바탕으로 `출발지 + 최대 이동시간 + 시간대 + 목적`을 입력하면 후보 상권을 랭킹해주는 모델 기반 프로토타입을 구축한다.**

---

# 1. 프로젝트 배경

## 1.1 장기적으로 만들고 싶은 서비스

장기적으로는 사용자가 단순히 “어디 갈까?”를 검색하는 것이 아니라, 자신의 **현실적인 이동 제약과 작은 목적만 입력하면 갈 만한 장소와 일정을 추천받는 지도 기반 서비스**를 만들고자 한다.

예시 입력:

```text
사용자 A 위치: 한국외대
사용자 B 위치: 수원
각자 최대 이동 가능 시간: 50분
환승: 최대 2회
도보: 최대 10~15분
목적: "짬뽕 먹고 싶다"
추가 희망: 밥 먹고 카페나 산책
```

장기 서비스가 해야 할 일:

```text
사용자 위치·교통 제약
        ↓
각 사용자의 Reachable Area 생성
        ↓
공통 후보지역 생성
        ↓
후보지역별 목적 적합도 + 실제 소비자 선택 패턴 평가
        ↓
후보 상권 랭킹
        ↓
구체적 매장/POI 추천
        ↓
코스 및 일정 생성
```

다만 **DAT 캡스톤에서는 이 서비스를 완성하는 것이 목표가 아니다.**

창업동아리에서는 실제 제품 구현을 진행할 수 있으므로, DAT에서는 서비스의 핵심 질문 중 하나인 아래 문제를 **외부 데이터셋을 통해 실증적으로 분석하는 것**이 목적이다.

> **"사람들은 갈 수 있는 여러 지역 중 왜 특정 목적지를 선택하는가?"**

---

# 2. DAT 프로젝트로서의 목표

DAT 프로젝트의 중심은 서비스 개발이 아니라 다음 과정을 충분히 경험하는 것이다.

```text
외부 Raw Data 확보
→ 대규모 데이터 전처리
→ 데이터셋 간 JOIN
→ Feature Engineering
→ EDA
→ 통계적 가설 검정
→ 공간 시각화
→ 예측 모델
→ 설명 가능성 분석
→ 최소 프로토타입
```

즉 결과물은 앱 그 자체가 아니라:

1. **실제 소비 목적지 선택에 대한 통계적 인사이트**
2. **우리가 직접 구축한 분석용 데이터마트**
3. **지도/그래프 기반 시각화**
4. **사용자 입력에 따라 후보 상권을 랭킹하는 모델**
5. **추천 이유를 설명할 수 있는 프로토타입**

이어야 한다.

---

# 3. 핵심 연구 질문

## RQ1. 이동비용과 목적지 선택

> 이동시간이 길어질수록 특정 상권의 선택 및 유입은 감소하는가?

기본 가설:

```text
Travel Time ↑
→ Destination Choice ↓
```

단, 장기 서비스에서는 사용자가 최대 이동시간을 직접 입력하므로 **이동시간은 우선 후보군을 제한하는 Hard Constraint** 역할을 한다.

예:

```text
사용자 최대 이동시간 = 50분

50분 초과 상권 → 후보에서 제거
50분 이내 상권 → Ranking 대상
```

그렇다고 10분과 49분을 동일하게 취급할 수는 없으므로, 후보군 안에서도 이동시간은 여전히 비용 변수로 활용한다.

---

## RQ2. 이동시간이 비슷해도 왜 특정 상권이 선택되는가?

프로젝트의 가장 핵심적인 연구 질문.

예:

```text
출발지 → A 상권: 32분
출발지 → B 상권: 35분

그런데 실제 유입량:
A = 20,000
B = 7,000
```

이 차이를 설명하는 변수 탐색:

- 음식점 밀도
- 카페 밀도
- 소매업 밀도
- 특정 업종 전문성
- 업종 다양성
- 상권 매출
- 점포 수
- 프랜차이즈 비율
- 집객시설
- 상권 성장률
- 외부 소비자 유입 비율
- 연령·요일·시간대 특성

핵심 질문:

> **이동시간을 통제한 뒤에도 어떤 상권 특성이 사람을 끌어들이는가?**

---

## RQ3. 목적지 매력은 누구에게나 동일한가?

다음과 같은 heterogeneity를 분석한다.

- 연령
- 성별(데이터 가용 범위 내)
- 평일 / 주말
- 낮 / 저녁 / 밤
- 쇼핑 / 관광 / 기타 목적
- 출발지역

예:

```text
카페 밀도의 영향
20대 토요일 오후 → 매우 큼
40대 평일 오전 → 상대적으로 작음
```

이를 통해 **Interaction / Moderation Effect**를 분석할 수 있다.

---

## RQ4. 실제 이동은 실제 소비로 이어지는가?

생활이동 데이터와 카드소비 데이터를 결합하여:

> 사람이 많이 이동하는 상권이 실제로도 외부 카드소비를 많이 발생시키는가?

를 분석한다.

Outcome 후보:

- 이동 유입량
- 카드 이용건수
- 카드 이용금액
- 외부 소비자 비중
- 방문거리/이동시간 대비 소비 효율

---

## RQ5. 실제 선택 행동을 예측할 수 있는가?

최종적으로는 다음 조건을 입력받아 후보 상권을 랭킹한다.

```text
출발 권역
요일
시간대
최대 이동 가능 시간
이동 목적
(향후) 음식 / 카페 / 쇼핑 / 문화 등 세부 목적
```

출력:

```text
1. 건대    0.84
2. 성수    0.79
3. 잠실    0.71
```

추가 설명:

```text
건대 추천 이유:
- 동일 조건의 20대 주말 유입이 높음
- 외식 점포 밀도 높음
- 카페 밀도 높음
- 이동시간 대비 카드 소비건수가 높음
```

---

# 4. 핵심 데이터셋

## 4.1 B078 수도권 생활이동 데이터

### 출처

서울특별시 빅데이터캠퍼스  
데이터셋: **B078 수도권 생활이동 데이터**

기간(확인 기준):
- 2023.01 ~ 2026.06

분석 환경:
- 서울 빅데이터캠퍼스
- 세부 원자료는 폐쇄망 데이터
- 결과 반출 심사 필요

초기 파이프라인/EDA는 서울 열린데이터광장의 공개 행정동 단위 수도권 생활이동 자료를 병행 활용 가능.

### 주요 필드

```text
ETL_YMD          기준일
O_CELL_ID        출발 250m 격자
O_CELL_X
O_CELL_Y
O_CELL_TP        출발지 유형

D_CELL_ID        도착 250m 격자
D_CELL_X
D_CELL_Y
D_CELL_TP        도착지 유형

ST_TIME_CD       출발시간
FNS_TIME_CD      도착시간

IN_FORN_DIV_NM   내/외국인

MOVE_PURPOSE     이동목적
MOVE_DIST        평균 이동거리(m)
MOVE_TIME        평균 이동시간(분)

MALE_xx_CNT      남성 연령별 이동량
FEML_xx_CNT      여성 연령별 이동량
```

### 이동 목적 코드

```text
1 출근
2 등교
3 귀가
4 쇼핑
5 관광
6 병원
7 기타
```

### 활용

- 출발지 → 목적지 OD
- 목적별 유입량
- 시간대별 유입량
- 연령별 이동 패턴
- 이동거리
- 평균 이동시간
- 목적지별 외부 유입 특성

---

# 4.2 B079 서울시민 업종별 카드소비 데이터

### 출처

서울특별시 빅데이터캠퍼스 + 신한카드  
데이터셋: **B079 서울시민의 업종별 카드소비 데이터**

기간(확인 기준):
- 2021.01 ~ 2026.06

폐쇄망 분석 데이터.

### 유용한 주요 파일 구조

#### 유형 A — 서울시민 일별/소비지역별

주요 컬럼:

```text
기준일자
가맹점주소광역시도
가맹점주소시군구
고객행정동코드
업종대분류
카드이용금액계
카드이용건수계
```

의미:

```text
어디 사는 사람이
→ 어디 지역에서
→ 어떤 업종에
→ 얼마를 소비했는가
```

#### 유형 B — 가맹점 지역 기준 유입지

주요 컬럼:

```text
기준일자
가맹점행정동코드
고객주소광역시도
고객주소시군구
업종대분류
카드이용금액계
카드이용건수계
```

의미:

```text
이 상권에 소비하러 온 사람들은
어느 지역에서 왔는가?
```

### 활용

- 상권별 외부 소비 유입 비율
- 소비자의 거주권역 → 소비 목적지 흐름
- 업종별 소비량
- 카드 이용금액
- 카드 이용건수
- 장거리 소비 비중
- 상권별 실제 소비 흡인력

### 중요한 해석

생활이동 데이터는:

```text
"사람이 이 지역으로 이동했다"
```

카드소비 데이터는:

```text
"타 지역 사람이 이 지역에서 실제 소비했다"
```

따라서 두 데이터를 결합하면 단순 이동을 넘어 **실제 소비 목적지 선택**에 접근할 수 있다.

---

# 4.3 서울시 상권분석서비스

### 출처

서울 열린데이터광장 / 서울신용보증재단

주요 활용 데이터:

- 점포-상권
- 추정매출-상권
- 상주인구
- 직장인구
- 생활인구
- 집객시설

### 점포 데이터 주요 변수

```text
기준_년분기_코드
상권_구분_코드
상권_코드
상권_코드_명

서비스_업종_코드
서비스_업종_코드_명

점포_수
유사_업종_점포_수
개업_율
개업_점포_수
폐업_률
폐업_점포_수
프랜차이즈_점포_수
```

### 활용 가능한 Feature

```text
restaurant_density
cafe_density
retail_density
culture_density

store_count
franchise_ratio
opening_rate
closure_rate

estimated_sales
sales_count

worker_population
resident_population
floating_population

attraction_facility_count
```

---

# 4.4 향후 추가 가능한 데이터

필수는 아니며 확장 단계에서 사용.

## 교통
- 지하철역 좌표
- 버스정류장
- 지하철 접근성
- 환승역 여부
- 역별 승하차량

## 관광
- 한국관광공사 TourAPI
- 관광지 정보
- 연관 관광지 데이터
- 관광 POI

## POI
- 소상공인시장진흥공단 상가업소 데이터
- 음식점
- 카페
- 상점
- 위경도
- 업종

## 날씨
- 기상청 단기/과거 관측 데이터

예:

```text
비 오는 날
→ 실내형 상권 선호 증가?
```

## 향후 제품용 실시간 교통 API
- TMAP
- ODsay
- 기타 지도 API

주의:
DAT 분석에서는 실시간 길찾기 API가 메인 데이터가 아니다.

---

# 5. 우리가 최종적으로 만들 데이터마트

원자료들을 결합하여 아래 형태의 분석 데이터셋을 구축하는 것이 핵심 Data Engineering 결과물이다.

```text
origin_id
destination_id
date
weekday
weekend
hour
age_group
gender
purpose
travel_time
travel_distance
mobility_inflow
card_spend_count
card_spend_amount
outside_consumer_ratio
restaurant_count
cafe_count
retail_count
culture_count
category_diversity
category_concentration
franchise_ratio
opening_rate
closure_rate
estimated_sales
resident_population
worker_population
floating_population
attraction_facility_count
destination_attraction_score
```

---

# 6. 주요 Feature Engineering

## 6.1 업종 다양성
- Shannon Entropy
- HHI

## 6.2 외부 소비자 유입률

```text
Outside Consumer Ratio
= 타 지역 거주자의 카드소비 / 해당 상권 전체 카드소비
```

## 6.3 이동시간 대비 Attraction

```text
Inflow per Travel Cost
```

같은 단순 효율 지표를 탐색적으로 생성 가능. 단, 최종 지표는 EDA 후 정의.

---

# 7. 핵심 자체 지표 아이디어
# Destination Attraction Score

넥서스 팀이 `이상 혼잡 점수`를 구축하는 것처럼 우리도 **자체 목적지 흡인력 지표**를 개발할 수 있다.

목표:

> 해당 지역이 자신의 주변 생활권뿐 아니라 외부 소비자를 얼마나 강하게 끌어들이는가?

가능한 구성 변수:
- 외부 지역 유입 비중
- 평균 이동시간
- 장거리 유입 비중
- 카드 이용건수
- 카드 이용금액
- 외부 카드소비 비중

초기 단순 형태:

```text
Destination Attraction
≈ External Inflow × Consumer Spending × Travel Cost
```

그러나 임의 가중치를 최종 모델로 사용하지 않는다.

권장:
1. z-score 표준화
2. 상관 구조 확인
3. PCA
4. Factor Analysis
5. 대표 component 또는 가중 합성지표 구성

---

# 8. 추가 자체 지표 아이디어
# Unexpected Attraction / Hidden Destination

먼저 baseline 모델로 기대 유입량을 예측한다.

```text
Expected Inflow
= f(travel_time, destination_size, store_count, population, ...)
```

그리고:

```text
Unexpected Attraction
= Actual Inflow - Expected Inflow
```

잔차가 큰 양수인 상권을 Hidden Destination으로 정의할 수 있다.

---

# 9. 통계 분석 로드맵

## Stage 1 — Descriptive Statistics / EDA
- 목적별 평균 이동시간
- 목적별 이동거리
- 연령별 목적지
- 평일 vs 주말
- 시간대
- 상권별 외부 유입
- 카드소비

## Stage 2 — 집단 차이
- t-test
- ANOVA
- Welch ANOVA
- Kruskal-Wallis

p-value뿐 아니라 effect size, 95% CI 병행.

## Stage 3 — Multiple Regression

```text
DestinationAttraction =
β0
+ β1 TravelTime
+ β2 CategoryDiversity
+ β3 CafeDensity
+ β4 RestaurantDensity
+ β5 FranchiseRatio
+ β6 Sales
+ β7 AttractionFacility
+ controls
```

## Stage 4 — Interaction / Moderation

예:
- CafeDensity × Age20s
- CategoryDiversity × Weekend
- RestaurantDensity × DinnerTime
- TravelTime × Purpose

## Stage 5 — Multilevel / Mixed Effects Model

예:
- Level 1: 시간대 / 요일 / 연령 / 목적
- Level 2: 상권
- Level 3: 자치구

## Stage 6 — Destination Choice Model
후보:
- Multinomial Logistic Regression
- Conditional Logit

## Stage 7 — Count Regression
Outcome이 이동량/소비건수라면:
- Poisson Regression
- Negative Binomial Regression

---

# 10. 공간 분석 / GIS

사용:
- GeoPandas
- QGIS
- Folium
- Plotly Map
- PySAL

분석:
- Destination Attraction 지도화
- Moran's I
- Local Moran's I
- Getis-Ord Gi*
- 필요 시 Spatial Lag Model
- 필요 시 Spatial Error Model

확장 질문:

> 하나의 핫플 상권이 주변 지역까지 소비자 유입을 증가시키는가?

---

# 11. Temporal 분석

질문:

> 목적지 매력은 시간대별로 달라지는가?

분석:
- Hour Fixed Effect
- Day-of-week Effect
- interaction
- panel regression

후속 확장:

> 성수는 언제부터 '동네 상권'이 아니라 '찾아가는 상권'이 되었는가?

후보:
- Panel Data
- Change Point Detection
- Interrupted Time Series
- clustering

---

# 12. ML 모델링

통계가 주 분석이며 ML은 확장 분석이다.

Baseline:
- 거리/시간 순 추천
- Historical Inflow Ranking
- Logistic / Multinomial Logistic Regression

ML 후보:
- Random Forest
- XGBoost
- LightGBM
- CatBoost

Explainability:
- Feature Importance
- SHAP

---

# 13. 추천 시스템 설계

```text
[사용자 입력]
출발지
요일
시간
최대 이동 가능 시간
목적

        ↓

[Candidate Filtering]
Travel Time <= 사용자 입력값

        ↓

[Destination Ranking Model]
이동비용
+
상권 특성
+
실제 과거 유입
+
실제 카드소비
+
사용자 조건

        ↓

[TOP K]
1. 건대
2. 성수
3. 잠실

        ↓

[Explanation]
추천 이유 TOP 3
```

중요:

사용자가 `50분까지 갈 수 있어`라고 입력하면 50분은 모델이 추정하는 값이 아니라 **Hard Constraint**다.

---

# 14. 추천 모델 평가

Ranking Metric:
- Recall@K
- Precision@K
- Hit Rate@K
- NDCG@K
- MRR

Business/Utility Metric:
- 거리순 Baseline 대비 개선
- 인기순 Baseline 대비 개선
- Coverage
- Diversity

---

# 15. 최종 프로토타입

추천:
- Streamlit

입력:
- 출발지역
- 요일
- 시간대
- 최대 이동시간
- 목적

출력:
- 지도
- TOP 5 상권
- 선택확률/적합도
- 추천 이유
- 예상 이동시간
- 유사집단 유입
- 업종 특성
- 카드 소비 특성

---

# 16. LLM 활용

LLM은 필수가 아니다.

사용할 경우:
- SHAP / 통계 결과를 자연어로 설명
- 목적지를 임의로 선택하지 않음

예:

```text
성수는 이동시간이 다소 길지만,
20대 주말 방문 비중과 카페·소매 다양성이 높아
현재 조건에서 높은 순위로 추천되었습니다.
```

---

# 17. 팀원 역량 및 희망사항

## 팀원 A — NLP/분석 경험자

경험:
- 데이터베이스 / SQL
- NLP
- 머신러닝/딥러닝 기초
- R
- 회귀/선형분석/시계열
- Python 데이터 수집/분석
- 정규표현식
- 영어 텍스트 전처리

프로젝트 경험:
- 29CM 댓글 Selenium 크롤링·감성분석
- SNS 해시태그 연구: X 10년치 데이터, 감성분석, RM-ANOVA, Python/R/Tableau
- 파파고 스페인어권 시장 전략: Reddit 감성분석, Google Trends, 트래픽 분석

희망:
- NLP, 특히 감성분석에 경험이 집중되어 새로운 통계 분석을 경험하고 싶음
- DA / DBA 취업 대비 경영·마케팅 프로젝트 희망
- AI 모델링에도 관심

추천 학습:
- Interaction
- Mixed Effect Model
- PCA / Factor Analysis
- Choice Model
- 공간통계
- ML Explainability

## 팀원 B
- 통계/AI 정규 교과 경험 부족
- 체계적 분석 경험 부족
- 질문하며 역량 강화 희망

권장:
EDA → 기술통계 → 가설검정 → 회귀 → 모델 평가

## 팀원 C
- Python 기본 문법 수준
- 프로젝트 경험 거의 없음

권장:
데이터 로딩 → 결측처리 → 날짜/코드 전처리 → pandas merge/groupby → 시각화 → feature engineering

## 팀원 D
관심:
- 경영/마케팅
- 소비자 행동
- 시장 수요
- 고객 세분화
- 광고 성과
- 신제품 수요예측
- 소비자 반응

희망:
- 수치 결과를 기업 전략·서비스 개선과 연결

권장 역할:
- 연구질문
- 선행연구
- 마케팅 프레이밍
- 변수 정의
- 결과 해석
- Managerial Implication

---

# 18. 팀 전체 설계 원칙

팀 내 경험 격차가 존재한다.

따라서 분석 난도를 계단식으로 설계한다.

```text
EDA
↓
기초 통계
↓
가설검정
↓
다중회귀
↓
Interaction
↓
Mixed Effect / Choice Model
↓
ML
↓
SHAP
```

한 사람이 코드를 전부 작성하고 나머지가 발표하는 구조를 피한다.

---

# 19. 경영·마케팅 관점

핵심 개념:
- Trade Area
- Consumer Spatial Choice
- Destination Marketing
- Consumer Segmentation
- Location Strategy

---

# 20. 얻고 싶은 비즈니스 인사이트

1. 이동시간이 비슷한데 더 많은 사람을 끌어들이는 상권은 무엇이 다른가?
2. 상권 특성 중 실제 외부 소비와 가장 관련이 높은 요소는 무엇인가?
3. 다양한 상권이 좋은가, 특정 목적에 전문화된 상권이 좋은가?
4. 프랜차이즈 비중이 높을수록 외부 유입은 증가/감소하는가?
5. 연령대별로 찾아가는 상권의 특성이 다른가?
6. 같은 지역도 시간대에 따라 목적지 매력이 달라지는가?
7. 접근성이 좋지 않아도 소비자를 끌어들이는 Hidden Destination은 어디인가?

---

# 21. 장기 프로젝트에 활용되는 방식

DAT:

```text
실제 이동행동
+
실제 소비
+
상권 특성
        ↓
사람들이 목적지를 선택하는 패턴 학습
        ↓
Candidate Ranking Model
```

향후 창업 프로젝트:

```text
사용자 A 위치
사용자 B 위치

각자:
최대 이동시간
환승
도보

+
"짬뽕 먹고 싶다"

        ↓

실시간 교통 API

        ↓

공통 Reachable Area

        ↓

DAT Candidate Ranking Model

        ↓

지역 TOP K

        ↓

POI 검색

        ↓

짬뽕집 + 카페 + 산책

        ↓

일정 생성
```

---

# 22. 장기 서비스 철학

> **"떠나고 싶은 마음만 있으면 떠날 수 있게"**

입력을 최소화:
- 현재 위치
- 갈 수 있는 시간
- 교통 제약
- 작은 목적

예:
- "1시간 있어"
- "환승 2번까지만"
- "많이 걷기 싫어"
- "짬뽕 먹고 싶어"

시스템은:
- 갈 수 있는 곳
- 갈 이유가 있는 곳
- 할 것

을 제시.

---

# 23. 향후 제품 확장

## Multi-user Meeting
A와 B의 Reachable Area 교집합을 만들고:
- 공정성
- 상권 매력
- 목적 적합도
평가.

## 교통 Preference
- 최대 시간
- 환승 수
- 도보
- 선호 교통수단

## Fine-grained Intent
현재 DAT의 쇼핑/관광에서:
- 짬뽕
- 스시
- 전시
- 카페
- 산책
- 쇼핑
- 데이트
- 혼술
등으로 확장.

## Itinerary
- 맛집 → 카페 → 전시 → 산책
- Graph / Route Optimization / Contextual Recommendation

## Personalization
사용자 feedback으로:
- Learning to Rank
- Contextual Bandit
- Preference Learning

## Multi-objective Recommendation

maximize:
- 장소 매력
- 목적 적합도
- 개인 취향

minimize:
- 이동시간
- 환승
- 도보
- 혼잡
- 비용

---

# 24. 프로젝트 Phase

## Phase 0 — Feasibility
- B078 접근
- B079 접근
- 행정동 코드 확인
- 공개 sample
- 상권 schema 확인

산출물:
- data_schema.md
- sample_head.csv
- join_key_test.ipynb

## Phase 1 — Data Pipeline
- Raw import
- encoding
- dtype
- missing
- code normalization
- geographic lookup
- aggregation
- join

산출:
- processed_od.parquet
- processed_card.parquet
- processed_commercial.parquet
- model_dataset.parquet

## Phase 2 — EDA
- 목적 × 이동시간
- 목적 × 연령
- 시간대 × 목적지
- 상권 × 외부 유입
- 상권 × 카드소비

## Phase 3 — Statistics
1. 기초가설
2. 집단차이
3. regression
4. interaction
5. mixed effect
6. count / choice model

## Phase 4 — Spatial
- Moran's I
- hotspot
- spillover

## Phase 5 — ML
- baseline
- XGBoost / LightGBM / CatBoost
- cross validation
- SHAP

## Phase 6 — Recommendation
입력:
- origin
- max_time
- purpose
- hour
- day
- age_group(optional)

출력:
- TOP K destination
- score
- explanation

## Phase 7 — Prototype
- Streamlit
- 최소 UI
- 분석 중심

---

# 25. 추천 Repository 구조

```text
dat-destination-choice/
│
├── README.md
├── PROJECT_CONTEXT.md
├── requirements.txt
│
├── data/
│   ├── raw/
│   ├── interim/
│   ├── processed/
│   └── external/
│
├── notebooks/
│   ├── 00_data_audit.ipynb
│   ├── 01_mobility_eda.ipynb
│   ├── 02_card_eda.ipynb
│   ├── 03_commercial_eda.ipynb
│   ├── 04_join.ipynb
│   ├── 05_feature_engineering.ipynb
│   ├── 06_statistics.ipynb
│   ├── 07_spatial_analysis.ipynb
│   ├── 08_ml.ipynb
│   └── 09_recommendation.ipynb
│
├── src/
│   ├── config.py
│   ├── data/
│   ├── features/
│   ├── statistics/
│   ├── spatial/
│   ├── models/
│   └── recommender/
│
├── app/
│   └── streamlit_app.py
│
├── reports/
│   ├── figures/
│   ├── tables/
│   └── weekly/
│
└── tests/
```

---

# 26. 개발/분석 원칙

- 시간 기반 예측 시 미래 데이터를 train에 포함하지 않는다.
- 통계모델은 관계 해석, ML은 예측으로 목적을 구분한다.
- observational / aggregate data이므로 인과표현을 피한다.
- Ecological fallacy 주의.
- 실시간 교통시간과 historical MOVE_TIME을 혼동하지 않는다.
- 임의의 Destination Attraction 가중치를 결과처럼 사용하지 않는다.

---

# 27. 데이터 제약

## B078/B079
폐쇄망:
- 데이터 접근 승인
- 반출심사
- 로컬 개발 제한

따라서 Dual Pipeline 권장.

### Open Pipeline
공개 행정동 데이터로:
- 코드
- 함수
- EDA
- 모델 scaffold

### Secure Pipeline
빅데이터캠퍼스:
- 세부 250m
- 카드데이터
- 실제 분석

---

# 28. 주요 리스크

## Risk 1 — JOIN 단위
- B078: 250m grid
- B079: 행정동/시군구
- 상권: 상권 코드

해결:
- 행정동 geometry
- point-in-polygon
- spatial aggregation
- 행정동 단위 공통 mart 우선

## Risk 2 — Choice Set 정의
선택모형에는 선택하지 않은 후보도 필요.

후보:
- 동일 출발지에서 60분 이내 모든 목적지
- 일정 유입 이상 주요 상권

## Risk 3 — 이동시간
B078 MOVE_TIME은 실시간 경로시간이 아닌 관측 평균.

## Risk 4 — 목적 세분화
B078 목적은 쇼핑/관광 등 macro 수준.
세부 intent는 향후 POI/리뷰로 확장.

---

# 29. 기존 DAT 기수와 차별점

기존:
- 4기: AI 음식 추천 서비스
- 5기 카드: 대용량 카드고객 + ML + XAI
- 5기 TikTok: 외부수집 + 파생변수 + 통계검정
- 6기 카드: 카드 혜택 raw text + 전국 상점 + LLM + 공간DB + 앱

이번:
```text
대규모 공간/소비 raw data
→ 복수 데이터 JOIN
→ 자체 지표
→ 통계분석
→ 공간분석
→ ML
→ 추천 랭킹 prototype
```

통계와 경영·마케팅 인사이트가 중심.

---

# 30. 넥서스 프로젝트에서 참고할 구조

넥서스:
```text
행사 혼잡 정량화
→ 혼잡 예측
→ 경로 재랭킹
```

우리:
```text
상권 흡인력 정량화
→ 목적지 선택 요인 분석
→ 목적지 선택 예측
→ 후보지역 재랭킹
```

대응:
- 넥서스 이상 혼잡 점수 ↔ 우리 Destination Attraction Score
- 넥서스 혼잡 예측 ↔ 우리 Destination Choice Prediction
- 넥서스 우회 경로 ↔ 우리 Alternative Destination Ranking

---

# 31. 추천 최종 제목

## 옵션 A
**Where Do We Go? 수도권 생활이동·카드소비·상권 데이터를 활용한 소비 목적지 선택 요인 분석 및 추천 모델**

## 옵션 B
**갈 수 있는 곳은 많은데, 사람들은 왜 그곳을 선택하는가? — 수도권 소비 목적지 선택 요인 분석**

## 옵션 C
**Destination Attraction: 수도권 상권의 외부 소비자 흡인력 분석 및 목적지 추천 모델**

현재 A 추천.

---

# 32. 성공 기준

프로젝트 발표 마지막에 아래를 보여줄 수 있어야 한다.

1. **같은 이동비용에서도 이런 특성을 가진 상권이 더 많이 선택되었다.**
2. **그 효과는 특정 연령/시간/목적에서 더 강했다.**
3. **이 패턴을 반영한 모델이 단순 거리순·인기순보다 실제 목적지 선택을 더 잘 예측했다.**
4. 사용자 입력에 대해 TOP K 상권과 추천 근거를 보여준다.

---

# 33. Codex가 처음 해야 할 일

이 문서를 읽은 뒤 바로 모델을 구현하지 말 것.

1. Repository scaffold 생성
2. `docs/data_sources.md` 작성
3. 공개 sample 데이터부터 로딩 pipeline 설계
4. 공통 공간 분석 단위를 정하기 위한 schema audit
5. `model_dataset` grain 명시
6. 1차 EDA 계획 작성

추천 grain 예시:

```text
date × hour × origin_dong × destination_dong × age_group × purpose
```

모델 구현은 그 이후.

---

# 34. Codex 구현 시 금지사항

- 처음부터 UI를 만들지 말 것.
- 처음부터 XGBoost만 돌리지 말 것.
- 임의의 Destination Attraction 가중치를 최종 결과처럼 쓰지 말 것.
- 데이터가 없는데 sample 값을 실제 값처럼 만들지 말 것.
- aggregate 데이터를 개인 선택 데이터라고 표현하지 말 것.
- 통계적 연관성을 인과관계로 표현하지 말 것.
- 실시간 교통시간과 historical MOVE_TIME을 혼동하지 말 것.
- NLP/LLM을 억지로 핵심 모델에 넣지 말 것.

---

# 35. 프로젝트의 최종 철학

이 프로젝트의 질문은:

> **"어디가 인기 있는가?"**

가 아니다.

그리고:

> **"사람들은 몇 분까지 이동하는가?"**

도 아니다.

핵심은:

> **"사용자가 갈 수 있는 범위 안에서, 어떤 목적지가 왜 더 선택될 가치가 있는가?"**

DAT에서는 실제 이동과 소비 데이터를 통해 그 패턴을 배우고,

장기 서비스에서는 그 결과를 사용해:

> **누구나 떠나고 싶은 마음만 있으면 어디로 가야 할지 찾을 수 있게 하는 것**

이 최종 방향이다.
