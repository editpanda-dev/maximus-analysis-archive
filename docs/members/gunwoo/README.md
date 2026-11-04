# 김건우 작업 폴더

정리: 2026-11-04 · 브랜치 `gunwoo/notes`

막시무스 상권 랭킹을 **"학생이 몰랐지만 실제로 갈 만한 곳"** 추천으로 넓힌 작업의 입구다. 이 폴더에는 개인 기록만 둔다. 코드·데이터·설계 문서는 팀이 같이 쓰는 주제 폴더에 있고, 아래 문서 지도에서 찾아간다.

## 이 폴더에 있는 것

| 문서 | 내용 | 언제 읽나 |
|---|---|---|
| [`README.md`](README.md) | 이 문서. 한 일 요약, 문서 지도, 추후 방향 요약 | 처음 |
| [`research_summary.md`](research_summary.md) | 논리 흐름 중심 요약. 단계마다 왜 바꿨고 무엇을 대안으로 봤는지 | 전체 흐름을 알고 싶을 때 |
| [`research_log.md`](research_log.md) | 상세 기록. 숫자, 데이터 출처 총목록, 막힌 것, 브랜치 지도 | 근거나 수치를 확인할 때 |
| [`service_ideas.md`](service_ideas.md) | 서비스에 붙여 볼 아이디어 6개(콜드 스타트, 맥락, 롱테일, 데이터, 상권 단위, 니즈 시나리오) | 다음에 무엇을 만들지 고를 때 |
| [`roadmap.md`](roadmap.md) | 추후 연구 방향. 단기 / 중기 / 데이터 확보 시 / 보류, 팀 도움이 필요한 것 | 일정을 잡을 때 |

## 한 일 (2026-10-29 ~ 11-04)

```
1. 글캠·서울캠 30분 숨은 곳      '숨은'을 잴 방법이 없음 → 정의부터 다시
2. 상권 의외성 모델 SERP v0      설계 근거 논문을 원문으로 확인할 필요
3. 선행연구 검증 → SERP v1       상권이 넓어 어느 가게로 갈지 모름
4. 점포 단위 의외성 v0 → v1 규칙  리뷰 신호가 비어 있음
5. 리뷰 수집 방법 조사           공식 API 평판·키워드 방식으로 대체 설계
```

| 단계 | 질문 | 결과 | 상태 |
|---|---|---|---|
| 1. 캠퍼스 숨은 곳 | 캠퍼스에서 30분 안, 학생이 모르는 명소가 있나 | 글캠 30분 생활권은 모현·오포뿐(점포의 10%). 서울캠 786개 상권에 숨은 가게 태그 | 검증 전. ODsay 측정 89/773건에서 멈춤 |
| 2. SERP v0 | 늘 가던 곳(관성)과 다르지만 갈 만한 상권은 | 점수 = 관련성 R × 의외성 U, R 하위 60% 제외, MMR로 다양성 | 코드·테스트·결과 커밋 |
| 3. 검증 → v1 | 인용 논문 12편이 맞게 쓰였나 | 핵심 서술 3개 수정. 공간 거리 가점 삭제, 이동시간 구간별 3곳, 서울캠 출발 추가 | 해설서·Word 보고서 커밋 |
| 4. 점포 단위 | 상권 안 어느 가게로 가야 하나 | 2단계 결합(상권 → 점포). 매칭 정밀도 0.94, 관성 상권 겹침 0. v1 규칙(비목적지 제외 등) | v1은 로컬 실행 대기 |
| 5. 리뷰 수집 | 리뷰로 점포 신호를 채울 수 있나 | 네이버는 캡차 토큰 없이 첫 요청부터 429. robots.txt가 AI 봇을 막음 → 크롤링은 하지 않기로 함 | 공식 API 키 발급 대기 |

정확도는 주장하지 않는다. 정답 라벨이 없어서 프록시 백테스트, beyond-accuracy 지표, 반사실 시뮬레이션, 민감도만 돌렸다. 라벨은 설문으로 만든다([`roadmap.md`](roadmap.md) 1번).

## 문서 지도

경로는 저장소 루트 기준이다. 대괄호는 아직 원본 `main`에 병합되기 전 그 파일이 있는 브랜치다.

| 주제 | 설계·해설 | 코드 | 결과 |
|---|---|---|---|
| 캠퍼스 숨은 곳 `[codex/gunwoo/campus-hidden-spots]` | `docs/campus/` (README, 현황 보고서, 한계, 원천 출처) | `scripts/campus/모현/`, `scripts/campus/서울캠/` | `data/processed/campus_globalcampus/`, `campus_seoulcampus/` |
| 상권 의외성 SERP `[gunwoo/serendipity]` | `docs/serendipity/recommendation_design.md`, `model_explained.md`, `prior_research_notes.md`, `reports/model_report.docx` | `scripts/build_serendipity_ranking.py` | `data/processed/serendipity_ranking/` (서울캠 출발은 `hufs_seoul/`) |
| 점포 단위 추천 `[gunwoo/store-level]` | `docs/store_level/recommendation_options.md`, `validation_v0.md`, `v1_changes.md`, `docs/campus/seoul_store_raw_sources.md` | `scripts/store_level/`, `scripts/campus/서울캠/store_rules_v1.py`, `scripts/naver/` | `data/processed/store_level/` |
| 로컬 실행 지시문 `[gunwoo/store-level]` | `docs/prompts/store_level_local_task_prompts.md`, `store_level_v1_local_run.md` | | |

## 추후 방향 (요약)

자세한 내용과 순서는 [`roadmap.md`](roadmap.md)에 있다.

1. **통합 설문 한 번으로 라벨 만들기**: 점포 카드, 상권 Kotkov 3문항, 니즈 시나리오 문항을 학생 30~50명에게 한 번에 묻는다. 가중치 학습, 니즈 우선순위, 실제 관성을 한꺼번에 얻는다.
2. **점포 v1 로컬 실행과 매칭 검수 50곳**: 이미 만든 규칙의 실제 영향을 확인한다.
3. **니즈 시나리오 추천**: 지금 데이터로 표현되는 카공(C1), 데이트(C5), 야식(M5)부터 만든다.
4. **콜드 스타트 카드 5장**: 설문 문항을 앱 첫 화면으로 그대로 옮긴다.
5. **공식 API 평판·키워드**: 카카오 로컬 + 네이버 블로그 검색으로 점포의 빈 리뷰 항을 채운다.

## 이어받는 사람을 위한 메모

- 원천 데이터와 API 응답은 저장소에 없다. 로컬 작업 폴더의 `데이터/` 아래에 있고, 스크립트는 `MAXIMUS_WORKSPACE` 환경변수로 그 폴더를 찾는다.
- 테스트는 `MAXIMUS_WORKSPACE`가 `데이터/` 폴더가 있는 곳을 가리켜야 시작된다. 빈 `데이터/` 폴더만 있어도 단위 테스트는 돈다.
- API 키는 `~/.config/maximus/keys.env` 환경변수로만 읽는다. 저장소에 넣지 않는다.
- 카카오 API 값(차 시간, 택시비, 지오코딩)은 재배포 조건을 아직 확인하지 않았다. 외부에 공유할 때 주의한다.
