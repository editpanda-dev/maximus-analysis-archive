# 점포 추천 시스템 한눈에 (v5, 2026-11-25)

김건우 · 막시무스 2단 추천의 **2단계(상권 → 점포)**. 상권 추천(1단계)이 "어디로 갈지"를 고르면, 이 시스템은 "거기서 어느 가게에 갈지"를 태그로 고른다.

스크립트 파일은 많지만 **하나의 파이프라인**이다. 스크립트마다 입력과 출력이 이어져 있어서, 아래 순서대로 돌리면 리뷰 원본에서 추천 목록까지 나온다. 파일이 나뉜 것은 단계마다 결과를 저장해 두고 다시 쓰기 위해서다(Jev 호출처럼 비싼 단계를 다시 돌리지 않도록).

## 1. 흐름

```
[1 수집]      네이버 플레이스 리뷰 (크롤러, PR #6)
                │  식사 30,371곳 · 리뷰 56.5만 / 카페 7,441곳 · 13.4만
                ▼
[2 정리]      매칭 판정 → 정제 → 상권 재부착
                build_naver_reviews.py (식사) · build_naver_reviews_cafe.py (카페)
                ▼
[3 피처]      키워드 칩 → 테마 점수 12개 (업종 안 순위)       build_label_round.py
              Jev 원자 판단 15개 (리뷰를 읽고 확률로 답함)    llm_judge/run_jev_all.py
              인허가 면적·업태, 프랜차이즈                    match_localdata.py · build_franchise_flags.py
                ▼
[4 라벨]      사람이 예/아니오로 찍음: 5회차 + 팀 2명, 1,212문항 · 가게 367곳
                build_label_round.py (후보 뽑기) · build_r5_group.py (단체 경계)
                ▼
[5 태그 모형] 태그별 로지스틱 → 확률 → 해당 / 애매 / 아님
                build_tags_v2.py (규칙 태그·허용표) → build_tags_v4.py (학습) → build_tags_v5.py (최신 라벨로 다시 학습)
              칩 적은 가게:  llm_judge/run_jev_textonly.py → build_vibe_textonly_v0.py
              카페:          build_cafe_tags_v0.py (칩 규칙, 라벨 전)
                ▼
[6 추천]      상권 추천 결과 + 점포 태그 → 상권별 "숨은 느좋" 가게
                pick_vibe_by_origin.py · build_area_review_table.py (상권 집계) · build_new_open_candidates_v0.py (신규 개업)
                ▼
[평가]        eval_tags_pooled.py (라벨러 간 일치·팀 라벨) · eval_tags_v5.py (새 피처) · eval_visit_info_v0.py (방문 정보)
```

## 2. 지금 결과 (`data/processed/store_level/recsys_v5/`)

| 무엇 | 규모 | 성능 |
|---|---|---|
| 식사 태그 v5 `store_tags_v5.csv` | 24,370곳, 태그 11개 | 느좋: 5회차 시험셋 가중 AUC 0.82, 가게 단위 CV 0.78 · 확정 구간 0.87 |
| 칩 적은 가게 느좋 `store_vibe_textonly_v0.csv` | 858곳 | 느좋 CV AUC 0.84 (칩 있는 가게용 v3는 0.88) |
| 카페 태그 v0 `cafe_tags_v0.csv` | 6,928곳, 태그 10개 | **라벨 검증 전** (칩 규칙) |
| 신규 개업 후보 `new_open_candidates_v0.csv` | 3,183곳 | 느좋 0.6+ · 비프랜차이즈 804곳 |
| 상권 리뷰 집계 `area_review_table_v1.csv` | 상권 773곳 | 태그 비율·리뷰 적은 느좋 가게 수 |

느좋 판정을 믿을 수 있는 정도 (학습에 안 쓴 가게 기준, 4·5회차 합계):

| 모형 확률 | 가게 수 | 실제 느좋 |
|---|---|---|
| 0.7 이상 | 31 | **90%** |
| 0.5 ~ 0.7 | 32 | 78% |
| 0.3 ~ 0.5 | 26 | 58% |
| 0.3 미만 | 27 | 37% |

모형이 "느좋"이라고 하면 대체로 맞다(0.7 이상 10곳 중 9곳). 문제는 반대쪽이다. "아님"(0.3 미만) 쪽에도 느좋이 3곳 중 1곳 섞여 있어서, 놓치는 가게가 많다. 추천은 정밀도가 중요하므로 0.6 이상만 보여 주는 지금 방식은 유지한다. 단, 표본이 116곳이라 구간마다 오차가 ±10~15%p다.

## 3. 문서

| 문서 | 내용 |
|---|---|
| [tags_v3_and_labels.md](tags_v3_and_labels.md) | v1~v3, 라벨 1~4회차, Jev 비교 (11-16) |
| [tags_v4_v5.md](tags_v4_v5.md) | 팀 라벨 합치기, 5회차 능동 학습, 단체 회식·감성 모임 정의, 방문 정보 1차 평가 |
| [cafe_textonly_new_open_v0.md](cafe_textonly_new_open_v0.md) | 카페 태그, 칩 적은 가게 본문 판정, 신규 개업 후보 |
| [../serendipity/serp_v1_campus_and_abc_compare.md](../serendipity/serp_v1_campus_and_abc_compare.md) | 1단계(상권) 쪽: 서울캠 출발 SERP, SERP-v1.2와 숨은 상권 ABC 방식 비교 |

## 4. 돌리는 법

스크립트는 개인 작업 폴더 사본이라 저장소 안에서 바로 돌지 않는다. 입력(리뷰 DB, 인허가, OD 원본)이 저장소 밖에 있다. 폴더 구조와 환경은 `scripts/members/gunwoo/workspace_2026_11/README.md`를 본다. 순서:

```bash
python 분석/build_naver_reviews.py              # 2 정리
python 분석/build_tags_v2.py <라벨 폴더> <후보.json> ...   # 5 규칙 태그 (3 테마 피처를 함께 만든다)
python 분석/llm_judge/run_jev_all.py            # 3 Jev (새 가게만 묻는다, 키 필요)
python 분석/build_tags_v5.py                    # 5 학습 태그 (v4 코드를 불러 쓴다)
python 분석/llm_judge/run_jev_textonly.py && python 분석/build_vibe_textonly_v0.py
python 분석/build_cafe_tags_v0.py
python 분석/build_new_open_candidates_v0.py
python 분석/build_area_review_table.py
python 분석/pick_vibe_by_origin.py serendipity_ranking_v1_2_1106089.csv 1106089 식사 전체   # 6 출발동 기준 추천
```

## 5. 한계

- **검증은 내 라벨 기준이다.** 라벨러 간 일치율 κ 0.59(느좋 0.74, 감성 모임 0.84, 단체 회식 0.18). 단체 회식은 사람끼리도 갈려서 정의를 다시 썼다(→ tags_v4_v5.md).
- **업종 편향.** 느좋 비율이 국·탕 0%, 경양식 94%다. 리뷰 칩이 업종마다 달라서 생기는 차이라서 업종 안 순위로 보정한 배지(`느좋_업종내`)를 따로 둔다.
- **카페 태그는 규칙만 있다.** 정확도 숫자가 없다.
- **방문 정보(동행·목적)는 아직 모형에 넣지 않았다.** 1차 평가에서 더해도 차이가 없었다(→ tags_v4_v5.md 6절).
