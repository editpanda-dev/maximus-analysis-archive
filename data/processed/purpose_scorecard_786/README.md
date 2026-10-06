# purpose_scorecard_786

786개 공식 상권의 5개 목적(식사·카페·공부·쇼핑·여가문화) 통합 점수표다. 재현: `python scripts/build_purpose_scorecard_786.py`

## 원천과 상태

| 목적 | 원천 | 상태 |
|---|---|---|
| 식사·쇼핑 | `food_shopping_v1` (김건우, 2026-10-06) | `official_v2` (10/1 Purpose Score v2 규칙) |
| 카페 | 장한별 9/29 초안, 잔차 방식 공급점수 | `provisional` |
| 공부 | 2주차 통합 `study_stay_current_score` (9/22) | `provisional` |
| 여가문화 | 지우진 `leisure_culture_v1` 9/30, 잔차 방식 | `provisional` |

카페·공부·여가 v2 파일이 올라오면 `scripts/build_purpose_scorecard_786.py`의 `SOURCES`에서 경로와 열 이름만 바꿔 다시 실행한다. 목적마다 계산 방식이 달라서, 모든 점수를 786개 안의 **백분위**(`*_pct`)로 바꾼 뒤 비교·조합한다.

## 파일

| 파일 | 내용 |
|---|---|
| `official_area_purpose_scorecard_786.csv` | 786행. 목적별 원점수·백분위·상태·추천 가능 여부, 가장 강한 목적과 목적 순서, 식사·쇼핑 하위분류, 식사 가격대(`food_price_tier`), 관광특구·소규모·넓은 상권·도매 플래그 |
| `purpose_combo_top10.csv` | 2개 목적 조합 10종 + 3개 목적 조합 10종의 Top 10. 동등 평균 백분위, 모든 목적 백분위 50 이상, 관광특구 폴리곤 제외, 30% 겹침 제거. 식사·쇼핑이 포함된 조합은 매출이 관측된 상권만. `provisional_purposes`에 임시 원천 목적 표시 |
| `purpose_scorecard_qa.json` | 행 수·중복·결측·조합 하한·목적 간 순위상관·원천 버전 |
