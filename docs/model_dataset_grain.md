# Model dataset grain 초안

## 권장 1차 grain

```text
date × hour × origin_dong × destination_dong × age_group × purpose
```

성별은 데이터 품질과 셀 억제 정도를 확인한 뒤 선택 차원으로 추가한다. 카드 데이터에 시간·연령·목적 차원이 없다면 억지로 세분하지 않고, 별도 outcome/feature mart로 유지한 뒤 공통 차원에서 결합한다.

## 논리 키

```text
date, hour, origin_dong_code, destination_dong_code, age_group, purpose_code
```

이 키의 유일성을 파이프라인 첫 단계에서 검증한다. 중복은 단순 제거하지 않고 성별, 내외국인, 원천 격자 등 누락된 차원이 있는지 먼저 확인한다.

## 측정값

- `mobility_inflow`: 해당 셀의 집계 이동량
- `travel_time_mean`: 원천 가중치를 확인한 뒤 계산한 평균 이동시간
- `travel_distance_mean`: 동일 원칙의 평균 이동거리
- `card_spend_count`, `card_spend_amount`: 가능한 공통 지역·날짜·업종 단위에서 결합
- 목적지 특성: 점포·업종 다양성·인구·집객시설 등 시점 기준 최신 과거 분기 값

## 파생 차원

- `weekday`, `is_weekend`
- 분석용 `time_band`(원본 `hour` 보존)
- 표준화된 `age_group`, `purpose`
- 지역코드 기준일/버전

## JOIN 원칙

1. 250m 격자 중심점을 행정동 경계에 point-in-polygon한다.
2. 경계선·미매칭 격자는 별도 플래그와 매칭률로 기록한다.
3. 카드 데이터가 시군구까지만 제공되면 행정동 값으로 임의 배분하지 않는다.
4. 분기 상권 특성은 관측일보다 미래인 정보를 붙이지 않는다.
5. 모든 JOIN 전후 행 수, key cardinality, 누락률, 측정값 합계를 비교한다.

## Choice model용 별도 long table

선택모형에는 선택된 목적지만으로는 부족하다. 출발지·조건별 도달 가능 후보를 생성해 아래 단위로 별도 테이블을 만든다.

```text
choice_event_or_stratum × candidate_destination
```

집계 데이터에서 `choice_event`를 개인 선택처럼 정의하지 않는다. 초기에는 출발지·일자·시간·연령·목적 strata 내 목적지 점유율 또는 count outcome을 사용하고, 후보군은 예컨대 60분 이내 및 최소 관측량 기준으로 사전 정의한다.
