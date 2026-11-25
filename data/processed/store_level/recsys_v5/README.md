# 점포 추천 시스템 v5 결과 (2026-11-25)

설명: `docs/store_level/README.md`. 리뷰 본문·작성자 닉네임은 들어 있지 않다(상호·점수만).

| 파일 | 행 | 내용 |
|---|---|---|
| `store_tags_v5.csv` | 24,370 | 식사 점포 태그. `p_<태그>` 확률, `tags` 해당 태그(`|`로 구분), `ambiguous` 애매 태그, `dropped` 아님, `느좋`·`느좋_업종내` 배지, `group_score` 단체 회식 규칙 점수, `franchise`, `rep_menu` |
| `jev_atomic_v1.csv` | 24,387 | Jev 원자 판단 15개(0~1 확률). 열 뜻은 `tags_v3_and_labels.md` |
| `store_vibe_textonly_v0.csv` | 858 | 칩 적은 가게의 느좋·데이트·감성 모임·가성비 혼밥 확률(본문 Jev 모형) |
| `jev_atomic_textonly_v1.csv` | 858 | 위 가게의 본문만 넣은 Jev 원자 판단 |
| `cafe_tags_v0.csv` | 6,928 | 카페 태그 10개(칩 규칙, 라벨 검증 전). `score_<태그>` 카페 내 백분위, `chain`, `takeout` |
| `new_open_candidates_v0.csv` | 3,183 | 2025년 이후 개업·영업 중 식사 점포. `open_date`, `p_느좋`, `vibe_source`(v5 / 본문 Jev / 빈칸) |
| `labels_r1_r5_team.csv` | 1,212 | 사람 라벨. `round`: r1-r4·r5(김건우), team(장한별·지우진 같은 55곳). 한 행 = 라벨러 1명의 답 1개 |
| `v5_eval.csv` | – | 새 피처 비교(5회차 시험셋 AUC) |
| `pooled_eval.csv` | – | 팀 라벨 합치기 평가 |
| `visit_info_eval_v0.csv` | – | 방문 정보 피처 1차 평가(AUC, 차이의 95% 구간) |
