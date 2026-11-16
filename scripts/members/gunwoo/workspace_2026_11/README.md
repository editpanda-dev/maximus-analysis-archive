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
| `serendipity_v1.py` | SERP-v1.2 (기본, R = 목적 점수). `--v11`이면 v1.1 |
| `serp_v1_validation.py` | v1.2 검증 4종: PATH-v0 비교, 리뷰 신호, 태그 필터, 시간 |
| `serp_v1_followup.py` | 대중교통 단계별 점수, 동료 모형 비교·보정, 성북 대학 빼고 학생 검증 |
| `student_flows.py`, `student_signal_by_*.py`, `hub_affinity.py` | 대학생 이동 근사, 왕십리 쏠림 점검 |

**점포: 태그와 라벨** → 문서 `docs/store_level/tags_v3_and_labels.md`

| 스크립트 | 하는 일 |
|---|---|
| `judge_naver_match.py`, `clean_naver_dining_reviews.py`, `build_naver_reviews.py`, `resolve_naver_place_conflicts.py` | 네이버 리뷰 매칭 판정·정제·상권 재부착 |
| `download_localdata.py`, `match_localdata.py` | 음식점 인허가 받기, 점포와 매칭(면적·업태) |
| `build_franchise_flags.py` | 프랜차이즈 판정 |
| `build_label_round.py`, `build_tag_review_csv.py`, `build_team_label_set.py` | 라벨 회차 후보, 허용표·제외 후보, 팀 라벨 세트 |
| `build_tags_v1.py` ~ `build_tags_v3.py` | 태그 모델 |
| `llm_judge/` | Jev·LLM·임베딩 판정 비교, Jev 전체 실행 |

`build_label_round.py`는 저장소 `scripts/store_level/build_keyword_theme_map_v0.py`의 테마 사전을 import한다.
