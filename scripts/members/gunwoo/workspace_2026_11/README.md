# 김건우 개인 작업 폴더 스크립트 (2026-11)

개인 작업 폴더의 `분석/`을 그대로 옮긴 사본이다. 입력 데이터(생활이동 OD 원본, 네이버 리뷰 DB, 인허가 등)가 저장소 밖에 있어서, 이 폴더에서 바로 돌아가지 않는다.

## 실행 위치

스크립트는 자기 위치의 한 단계 위를 작업 폴더로 본다(`Path(__file__).parents[1]`). 아래 구조에서 `분석/`에 두고 돌린다.

```
<작업 폴더>/
├── 분석/                      ← 이 폴더 내용
├── 데이터/원천, 데이터/가공, 데이터/검토
├── 수집/naver-review-crawler/crawler.db
└── maximus-analysis-archive/  ← 이 저장소 (scripts/build_serendipity_ranking.py 등을 import)
```

환경: `~/.venvs/maximus` (Python 3.11, pandas·geopandas·scikit-learn). 키는 환경변수(`SEOUL_OPENAPI_KEY`, `TYPESAFE_API_KEY`)로만 읽는다.

## 무엇이 무엇을 만드나

**상권: 실제 이동 평가와 SERP-v1** → 문서 `docs/serendipity/serp_v1_od_evaluation.md`

| 스크립트 | 하는 일 |
|---|---|
| `build_seoul_od_panel.py`, `build_ddm_od_panel.py` | 생활이동 OD에서 도착 '기타' 이동만 뽑아 월별 패널 |
| `build_dongdaemun_od_inflow.py` | 동대문구발 상권별 유입 |
| `elastic_net_v0.py` | Ridge·Lasso·Elastic Net·HistGB 비교, 계수 안정성 |
| `leisure_v1_align.py`, `serendipity_en_v0.py` | 여가 v1 규칙 정렬, EN판 의외성 |
| `eval_destination_ranking.py` | 시간 순 분할 평가 |
| `eval_generalization.py` | 구 홀드아웃 평가 (핵심) |
| `build_transit_time_matrix.py` | 출발동 × 상권 대중교통 시간 |
| `serendipity_v1.py` | SERP-v1.2 (기본, R = 목적 점수). `--v11`이면 v1.1, `--origin <행정동>`이면 출발동 하나 기준(11-24) |
| `eval_v1_scores.py`, `stability.py` | 규모 보정 v1 점수 평가, 안정성 |
| `pick_vibe_by_origin.py` | 출발동 기준 상권 top N + 상권별 숨은 느좋 가게 |
| `hidden_area_combined_v1.py` | **1단계 최종 제안**: 숨은 상권 ABC + SERP 관성·덜 감 필터 결합안 (저장소 자료만으로 돎) |
| `serp_v1_validation.py` | v1.2 검증 4종: PATH-v0 비교, 리뷰 신호, 태그 필터, 시간 |
| `serp_v1_followup.py` | 대중교통 단계별 점수, 동료 모형 비교·보정, 성북 대학 빼고 학생 검증 |
| `student_flows.py`, `student_signal_by_*.py`, `hub_affinity.py` | 대학생 이동 근사, 왕십리 쏠림 점검 |

**점포: 태그와 라벨** → 전체 흐름 `docs/store_level/README.md` (v1~v3 `tags_v3_and_labels.md`, v4·v5 `tags_v4_v5.md`, 확장 `cafe_textonly_new_open_v0.md`)

| 스크립트 | 하는 일 |
|---|---|
| `judge_naver_match.py`, `clean_naver_dining_reviews.py`, `build_naver_reviews.py`, `resolve_naver_place_conflicts.py` | 네이버 리뷰 매칭 판정·정제·상권 재부착 |
| `download_localdata.py`, `match_localdata.py` | 음식점 인허가 받기, 점포와 매칭(면적·업태) |
| `build_franchise_flags.py` | 프랜차이즈 판정 |
| `build_label_round.py`, `build_tag_review_csv.py`, `build_team_label_set.py` | 라벨 회차 후보, 허용표·제외 후보, 팀 라벨 세트 |
| `build_tags_v1.py` ~ `build_tags_v3.py` | 태그 모델 (옛 판) |
| `build_tags_v4.py`, `build_tags_v5.py` | 태그 모델 v4(팀 라벨 합침·단체 회식 규칙), v5(5회차 라벨·MIN_N 10). v5는 v4 코드를 불러 쓴다 |
| `build_tags_v5_1.py`, `eval_group_v1.py` | v5.1: 단체 회식 확률 보정·감성 모임 배타, 단체 회식 개선 후보 비교 |
| `build_r5_group.py` | 5회차 단체 회식 경계 표본 |
| `eval_tags_pooled.py`, `eval_tags_v5.py`, `eval_visit_info_v0.py` | 라벨러 간 일치·팀 라벨 효과, 새 피처 비교, 방문 정보 1차 평가 |
| `llm_judge/run_jev_textonly.py`, `build_vibe_textonly_v0.py` | 칩 적은 가게: 본문만으로 Jev → 느좋 등 확률 |
| `build_naver_reviews_cafe.py`, `build_cafe_tags_v0.py` | 카페 리뷰 정리, 카페 태그 v0(칩 규칙) |
| `build_new_open_candidates_v0.py` | 2025년 이후 개업 느좋 후보 |
| `build_area_review_table.py` | 상권 단위 리뷰·태그 집계표 |
| `llm_judge/` | Jev·LLM·임베딩 판정 비교, Jev 전체 실행 |

`build_label_round.py`는 저장소 `scripts/store_level/build_keyword_theme_map_v0.py`의 테마 사전을 import한다.
