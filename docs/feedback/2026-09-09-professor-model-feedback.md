# 교수님 피드백 아카이브 — 2026-09-09

## 원문

보관 이미지: `docs/feedback/assets/2026-09-09-professor-model-feedback.png`

> Team 04
>
> - I don’t why you need to use complex model in your recommendation.
> - I think it would be better to create the model with traditional machine learning and use the complex model for the early comparison.
> - I am not sure with the use of Frozen SBERT for the fine tuning while the data is more likely numeric and categorical data without text data.
> - Please find the previous work on this prediction model.

## 피드백 해석

1. 추천에 복잡한 딥러닝/LLM을 쓰는 연구상 필요성이 아직 입증되지 않았다.
2. 수치형·범주형 중심 데이터에는 전통 통계/ML을 주모형으로 두고, 복잡 모형은 비교 기준으로 제한해야 한다.
3. 원문 텍스트가 없는 현재 데이터에서 Frozen SBERT 임베딩·파인튜닝은 데이터-모형 적합성이 낮다.
4. 목적지 선택/공간 선택/이동-소비 예측의 선행연구를 찾아, 예측 단위·목표변수·baseline·평가법의 근거를 제시해야 한다.

## 현재 문서와의 정합성

- `docs/analysis_roadmap.md`에는 Logistic/Multinomial Logistic, LightGBM, CatBoost를 이미 후보로 두고 있어 이 방향을 주모형으로 확정한다.
- `docs/model_dataset_grain.md`의 분석 단위는 수치형·범주형 중심이므로 SBERT는 1주차 범위에서 제외한다.
- 복잡 모델은 성능 개선 가설을 검증하는 보조 비교 실험으로만 남기며, 성능·설명가능성·운영비에서 전통 ML보다 우위가 확인될 때만 채택한다.

## 1주차 의사결정

- 주 과제: `조건부 목적지 선택/랭킹` 문제를 명확히 정의한다.
- 주모형: 해석용 Conditional Logit 또는 Multinomial Logistic, 예측용 CatBoost 또는 LightGBM.
- baseline: 거리순, 전체 인기순, 동일 조건 과거 유입순.
- 보류: Frozen SBERT, LLM 임베딩, 파인튜닝, 복잡 딥러닝 모델.
- 비교 원칙: 복잡 모형은 동일한 train/validation/test 분할과 동일 후보군에서만 비교한다.

## 재검토 조건

- 합법적으로 이용 가능한 실제 리뷰 원문 등 비정형 텍스트가 확보된다.
- 텍스트 특징을 추가했을 때 시간 순 검증에서 NDCG@5/Recall@5가 전통 ML보다 일관되게 개선된다.
- 개선폭, 설명가능성, 추론비용을 함께 보고해 추가 복잡성을 정당화할 수 있다.
