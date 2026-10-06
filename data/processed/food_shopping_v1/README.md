# food_shopping_v1

식사·쇼핑 점수 기준선 v1 산출물이다. 방법은 [`docs/food_shopping_v1_method.md`](../../../docs/food_shopping_v1_method.md)에 있다. 재현은 `python scripts/build_food_shopping_v1.py --sbiz-zip <소상공인 ZIP>`로 한다.

| 파일 | 행 단위 | 내용 |
|---|---|---|
| `official_area_food_shopping_v1_786.csv` | 상권 786 | 식사·쇼핑 대분류와 하위분류 11개의 점포 수·밀도·특화도·백분위·매출 상태·점수. 최고 하위분류와 Top 3, 도매·관광특구·넓은/소규모 플래그, 추천 근거 문장(`food_reason`, `shopping_reason`), 임시 카페 점수 |
| `food_shopping_v1_purpose_top.csv` | 목록×순위 | 식사·쇼핑 Top 20(`*_full`, 매출 관측)과 Top 10(`*_supply_only`, 매출 결측 상권 별도 정렬). 관광특구 폴리곤 제외, 소규모 상권은 `small_area` 표시로 유지 |
| `food_shopping_v1_subtype_top.csv` | 하위분류×순위 | M1–M6, SH1–SH5 Top 10 (점포 5개 이상, 소규모 상권 제외) |
| `food_shopping_v1_combo_top.csv` | 조합×순위 | 식사+쇼핑, 식사+카페, 쇼핑+카페, 식사+카페+쇼핑 Top 10. `basis`는 `all_sales_observed`와 `includes_supply_only` 두 가지이고, 모든 목적이 백분위 50 이상인 상권만 올리며, 추천 근거 문장 포함 |
| `food_shopping_v1_score_breakdown_top.csv` | 상위 상권×목적 | 상권 안 밀도·도보권 밀도·특화도·매출 생산성 지수 백분위와 점수 기여분(합계 = 점수), 하위분류 점수 |
| `food_shopping_v1_tourism_scenarios.csv` | 대상×시나리오 | 관광특구 A/B/C별 Top 10과 유지·진입·이탈 |
| `food_shopping_v1_weight_sensitivity.csv` | 대상×가중치 | 공급·소비 50/70/80 × 접근률 0/10/20%에서 Top 10 유지 수와 순위상관 |
| `food_shopping_v1_top10_stability.csv` | 기준 Top 10 | 9개 가중치 조합 중 Top 10에 남은 횟수, 안정/탐색 |
| `food_shopping_v1_quarter_sensitivity.csv` | 대상×분기 | 2025년 1–3분기 점포·매출로 다시 계산했을 때 Top 10 유지 수와 순위상관 |
| `food_shopping_v1_lunch_price_cells.csv` | 상권×식사 업종 | 점심 객단가, 업종 중앙값 대비 가격 지수, 저가·중가·고가·정보없음 (필터 속성, 점수 미반영) |
| `food_shopping_v1_qa.json` | — | 786행·중복·결측·범위·업종 중복·플래그·크기 상관·배달 민감도 QA. `passed=true` |
| `maps/food_shopping_v1_top_map.html` | — | 식사·쇼핑 Top 20, 식사+쇼핑, 식사+카페+쇼핑 Top 10 레이어 지도 |
| `maps/food_shopping_v1_top_map_{seoul,central}.png` | — | 발표용 정적 지도 (서울 전체 / 도심 확대) |

입력 스냅샷:

- `data/reference/food_shopping/food_shopping_wholesale_review_2025q4.csv`: 도매 자동 후보 14곳의 수동 판정
- `data/reference/food_shopping/cafe_size_adjusted_score_draft_20260929.csv`: 장한별 `codex/hanbyeol/cafe-study-followup`(`fd9ca55`)의 카페 초안 점수 열. 조합용 임시값이다.
