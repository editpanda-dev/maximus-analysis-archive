# 막시무스 추천 시스템 한눈에 (상권 → 점포, 2026-11-25)

김건우 · 동대문구(회기역) 출발 대중교통 30분 안에서 "의외지만 갈 만한 상권"을 고르고, 그 상권 안에서 "목적에 맞는 가게"를 고르는 **2단 추천**이다.

| 단계 | 하는 일 | 현재 판 | 자세히 |
|---|---|---|---|
| 1 상권 | 목적(식사·카페·쇼핑·공부·여가문화)에 맞고, 동대문구민이 덜 가는 상권 10곳 | **숨은 상권 결합안 v1** (ABC 뼈대 + SERP 실제 이동 신호) | [../serendipity/hidden_area_combined_v1.md](../serendipity/hidden_area_combined_v1.md) |
| 2 점포 | 고른 상권 안 식당·카페에 태그(느좋·데이트·감성 모임·단체 회식 등)를 붙여 가게를 고름 | **점포 태그 v5.1** | 아래 2~5절 |

스크립트는 여러 개지만 **하나의 파이프라인**이다. 파일을 나눈 것은 단계마다 결과를 저장해 두고 다시 쓰기 위해서다(Jev 호출처럼 비싼 단계를 다시 돌리지 않도록).

## 1. 흐름

```
[1단계 상권]
  공식 상권 786곳 ─ 30분 도달률 ≥ 0.5 ─ 늘 가던 곳 빼기(가까운·매출 큰·실제로 많이 가는 곳)
                 ─ 8달 중 7달 이상 덜 간 곳만 ─ 목적 점포 비율(A1) 순위 ─ 매출 하위 4곳 보장 ─ MMR로 고르게
                 → 목적별 상권 10곳                                         hidden_area_combined_v1.py
                                   │
[2단계 점포]                        ▼
  [수집]  네이버 플레이스 리뷰 (크롤러, PR #6): 식사 30,371곳 · 리뷰 56.5만 / 카페 7,441곳 · 13.4만
  [정리]  매칭 판정 → 정제 → 상권 재부착             build_naver_reviews.py · build_naver_reviews_cafe.py
  [피처]  키워드 칩 → 테마 점수 12개(업종 안 순위)     build_label_round.py
          Jev 원자 판단 15개(리뷰를 읽고 확률로 답함)  llm_judge/run_jev_all.py
          인허가 면적·업태, 프랜차이즈                match_localdata.py · build_franchise_flags.py
  [라벨]  사람이 예/아니오: 1~5회차 + 팀 2명, 1,212문항 · 367곳   build_label_round.py · build_r5_group.py
  [모형]  태그별 로지스틱 → 확률 → 해당 / 애매 / 아님
          build_tags_v2.py(규칙·허용표) → build_tags_v4.py(학습) → build_tags_v5.py(5회차 라벨) → build_tags_v5_1.py(단체·감성 배타)
          칩 적은 가게: llm_judge/run_jev_textonly.py → build_vibe_textonly_v0.py
          카페: build_cafe_tags_v0.py (칩 규칙, 라벨 전)
  [추천]  상권 + 점포 태그 → 상권별 "숨은 느좋" 가게    pick_vibe_by_origin.py
          상권 리뷰 집계 · 신규 개업 후보              build_area_review_table.py · build_new_open_candidates_v0.py
  [평가]  eval_tags_pooled.py · eval_tags_v5.py · eval_visit_info_v0.py · eval_group_v1.py
```

## 2. 점포 결과 (`data/processed/store_level/recsys_v5/`)

| 무엇 | 규모 | 성능 |
|---|---|---|
| 식사 태그 v5.1 `store_tags_v5_1.csv` | 24,370곳, 태그 11개 | 느좋: 처음 보는 5회차 시험셋 AUC 0.82 · 가게 단위 CV 0.78 |
| 칩 적은 가게 느좋 `store_vibe_textonly_v0.csv` | 858곳 | 느좋 CV AUC 0.84 |
| 카페 태그 v0 `cafe_tags_v0.csv` | 6,928곳, 태그 10개 | **라벨 검증 전** (칩 규칙) |
| 신규 개업 후보 `new_open_candidates_v0.csv` | 3,183곳 | 느좋 0.6+ · 비프랜차이즈 804곳 |
| 상권 리뷰 집계 `area_review_table_v1.csv` | 상권 773곳 | 태그 비율·리뷰 적은 느좋 가게 수 |

**느좋 판정을 믿을 수 있는 정도** (학습에 안 쓴 4·5회차 가게 116곳)

| 모형 확률 | 가게 | 실제 느좋 |
|---|---|---|
| 0.7 이상 | 31 | **90%** |
| 0.5 ~ 0.7 | 32 | 78% |
| 0.3 ~ 0.5 | 26 | 58% |
| 0.3 미만 | 27 | 37% |

모형이 느좋이라고 하면 대체로 맞다. 약점은 놓치는 쪽이다(0.3 미만에도 3곳 중 1곳이 느좋). 추천에서는 정밀도가 중요하므로 0.6 이상만 보여 주는 방식을 유지한다. 구간마다 오차는 ±10~15%p다.

## 3. 감성 모임과 단체 회식은 겹치지 않는다 (v5.1)

두 태그는 "여럿이 가는 곳"이라는 점이 같아서 자주 함께 붙었다. v5.1부터는 **한 가게에 둘 중 하나만** 붙는다.

- 두 태그를 모두 받을 만한 가게는 **확률이 높은 쪽 하나만** 남기고, 다른 쪽은 `dropped`로 옮긴다. 판단 기록은 `exclusive_note`에 있다.
- 단체 회식 확률(`p_단체 회식`)은 규칙 점수를 라벨로 보정한 값이다. 그래서 감성 모임 확률과 같은 잣대로 비교할 수 있다.
- 결과: 1,740곳을 정리했다(단체 남김 891 · 감성 남김 849). 이제 겹치는 가게는 0곳이다. 라벨에서 둘 중 하나만 '예'인 가게 12곳으로 맞혀 보면, 한쪽을 고른 판정이 11곳 맞았다.
- 정의(자리·먹는 방식·소리)와 개선 실험은 [tags_v4_v5.md](tags_v4_v5.md) 3·7절에 있다.

## 4. 문서

| 문서 | 내용 |
|---|---|
| [../serendipity/hidden_area_combined_v1.md](../serendipity/hidden_area_combined_v1.md) | **1단계 최종**: 숨은 상권 결합안, ABC·SERP와 비교 |
| [../serendipity/serp_v1_campus_and_abc_compare.md](../serendipity/serp_v1_campus_and_abc_compare.md) | 서울캠 출발 SERP, 결합안을 정하게 된 비교 |
| [tags_v3_and_labels.md](tags_v3_and_labels.md) | 태그 v1~v3, 라벨 1~4회차, Jev 비교 (11-16) |
| [tags_v4_v5.md](tags_v4_v5.md) | 팀 라벨, 5회차 능동 학습, 단체 회식 개선·배타, 방문 정보 1차 평가 |
| [cafe_textonly_new_open_v0.md](cafe_textonly_new_open_v0.md) | 카페 태그, 칩 적은 가게 본문 판정, 신규 개업 후보 |

## 5. 돌리는 법

스크립트는 개인 작업 폴더 사본이라 저장소 안에서 바로 돌지 않는다. 입력(리뷰 DB, 인허가, OD 원본)이 저장소 밖에 있다. 폴더 구조와 환경은 `scripts/members/gunwoo/workspace_2026_11/README.md`를 본다. 1단계 결합안은 저장소 자료만으로 돈다.

```bash
# 1단계 상권 (저장소 자료만 필요)
python 분석/hidden_area_combined_v1.py <저장소>/data/processed/ <출력 폴더>

# 2단계 점포
python 분석/build_naver_reviews.py                          # 정리
python 분석/build_tags_v2.py <라벨 폴더> <후보.json> ...     # 규칙 태그 (테마 피처를 함께 만든다)
python 분석/llm_judge/run_jev_all.py                        # Jev (새 가게만 묻는다, 키 필요)
python 분석/build_tags_v5.py && python 분석/build_tags_v5_1.py
python 분석/llm_judge/run_jev_textonly.py && python 분석/build_vibe_textonly_v0.py
python 분석/build_cafe_tags_v0.py
python 분석/build_new_open_candidates_v0.py
python 분석/build_area_review_table.py
python 분석/pick_vibe_by_origin.py serendipity_ranking_v1_2_1106089.csv 1106089 식사 전체
```

## 6. 한계

- **검증은 주로 내 라벨 기준이다.** 라벨러 간 일치율은 κ 0.59다(느좋 0.74, 감성 모임 0.84, 단체 회식 0.18).
- **단체 회식 기준선은 임시값이다.** 라벨이 단체 후보 위주로만 있어서, 서울 식당 중 몇 %가 진짜 단체 회식 가게인지 모른다. 지금은 18%(4,428곳)가 해당이다. 무작위 가게 30곳 라벨이 필요하다.
- **업종 편향.** 느좋 비율이 국·탕 0%, 경양식 94%다. 업종 안 순위 배지(`느좋_업종내`)를 따로 둔다.
- **카페 태그는 규칙만 있다.** 정확도 숫자가 없다.
- **의외성이 좋은 추천인지는 아직 모른다.** 1단계 결합안은 "덜 간다"를 실제 이동으로 확인했다. 하지만 학생이 실제로 반기는지는 설문(카드 30세트 준비됨)으로 봐야 한다.
