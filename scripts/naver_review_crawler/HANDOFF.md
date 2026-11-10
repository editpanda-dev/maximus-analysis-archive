# 네이버 플레이스 리뷰 수집 — 3인 분담 인수인계

상권–점포 매핑(`data/processed/area_store_mapping/area_store_20260630.zip`)의 점포 219,859곳에 대해 네이버 플레이스 방문자 리뷰를 점포당 최대 20건 수집한다. 혼자 돌리면 약 19일(점포당 약 7.5초)이라 세 명이 나눠 돌린다.

작성: 김건우, 2026-11-10 기준.

## 1. 현재 진행 상황 (2026-11-10 12:40)

| 목적 | 점포 | 진행 |
|---|---|---|
| food (식사) | 40,636 | 7,600곳 처리 완료(리뷰 수집 5,191곳, 약 9.6만 건), 김건우 맥에서 계속 수집 중 |
| cafe · study · leisure · shopping | 63,345 | 미착수 |
| none (목적 태그 없음) | 115,878 | 미착수 |

> 23만 건은 매핑의 **상권–점포 연결 행 수(237,718)**다. 한 점포가 여러 상권에 걸치면 여러 번 세기 때문에, 수집 단위인 고유 점포는 219,859곳이다.

## 2. 분담

몫은 `--purposes`(목적)와 `--shard/--num-shards`(점포 ID 해시)로 나눈다. 해시는 누구 컴퓨터에서 계산해도 같으므로 **각자 자기 DB를 따로 써도 겹치지 않는다.**

**1단계: 핵심 목적** (각자 약 3만 2천 곳, 약 3일)

| 담당 | 몫 | 실행 인자 |
|---|---|---|
| A 김건우 | food 남은 약 3.3만 곳 (이미 진행 중) | `--purposes food` |
| B ____ | cafe·study·leisure·shopping의 절반 (약 3.2만 곳) | `--purposes cafe,study,leisure,shopping --shard 0 --num-shards 2` |
| C ____ | 위와 같은 목적의 나머지 절반 (약 3.2만 곳) | `--purposes cafe,study,leisure,shopping --shard 1 --num-shards 2` |

**2단계: 목적 태그 없는 점포** (각자 약 3.9만 곳, 약 3.5일). 1단계가 끝난 사람부터 시작한다.

| 담당 | 실행 인자 |
|---|---|
| A | `--purposes none --shard 0 --num-shards 3` |
| B | `--purposes none --shard 1 --num-shards 3` |
| C | `--purposes none --shard 2 --num-shards 3` |

2단계는 분석에 꼭 필요한지 먼저 팀에서 정한다(미분류는 목적 태그가 없는 점포라 추천에 바로 쓰이지 않을 수 있다).

## 3. 꼭 지킬 것 (차단 방지)

1. **한 인터넷 회선(IP)에서는 한 사람만 돌린다.** 같은 와이파이(학교·카페·집)를 쓰는 두 사람이 동시에 돌리면 네이버에는 한 사람이 두 배 속도로 긁는 것처럼 보여 바로 차단된다. 각자 집 회선에서 돌린다.
2. **한 컴퓨터에서 실행기는 하나만.** `overnight.sh`를 두 번 띄우지 않는다.
3. **지연·휴식 값을 줄이지 않는다.** 점포 사이 2~3초, 100곳마다 25초, 500곳마다 4분 휴식이 들어가 있다.
4. **맥은 충전기를 꽂고 덮개를 연 채로.** 배터리 상태이거나 덮개를 닫으면 잠자기 방지가 듣지 않아 수집이 멈춘다(멈춰도 데이터는 안전하고, 깨어나면 이어서 한다).
5. 결과 DB와 CSV는 **저장소에 커밋하지 않는다.** 리뷰에 작성자 닉네임이 들어 있고 저장소는 공개다(`.gitignore`에 넣어 둠).

## 4. 설치 (처음 한 번, 맥 기준)

```bash
git fetch origin
git checkout codex/gunwoo/naver-review-crawler
cd scripts/naver_review_crawler
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python import_stores.py          # 점포 21.9만 곳을 crawler.db에 적재 (1분 내외)
```

Python 3.9 이상. 윈도우는 `.venv\Scripts\python.exe`로 바꿔 쓰고, `overnight.sh`는 Git Bash에서 `PY=.venv/Scripts/python.exe ./overnight.sh ...`로 실행한다(잠자기 방지는 직접 설정).

## 5. 실행

**먼저 5곳만 시험** (본인 몫 인자를 그대로 붙인다):

```bash
.venv/bin/python run_crawler.py --limit 5 --purposes cafe,study,leisure,shopping --shard 0 --num-shards 2
```

`✨ [수집 20건]`이 몇 줄 나오면 정상이다. 그다음 무인 실행:

```bash
nohup ./overnight.sh --purposes cafe,study,leisure,shopping --shard 0 --num-shards 2 > /dev/null 2>&1 &
```

- 로그: `logs/overnight_*.log`
- 멈추기: `kill $(cat logs/overnight.pid)` (진행 상태는 DB에 바로 저장되므로 언제 멈춰도 된다)
- 다시 시작: 같은 명령을 다시 실행. PENDING인 점포부터 이어서 한다.

진행 확인:

```bash
sqlite3 crawler.db "SELECT purpose, review_status, count(*) FROM excel_dining_stores GROUP BY 1,2"
sqlite3 crawler.db "SELECT count(*) FROM reviews"
```

## 6. 실행기가 알아서 하는 것

| 상황 | 동작 |
|---|---|
| 차단 화면 / HTTP 403·429 | 해당 점포는 PENDING 그대로, 배치를 즉시 멈춤 → 30분 대기 후 재개(차단이 반복되면 대기를 2배씩, 최대 2시간) |
| 로딩 실패·타임아웃 | PENDING 유지, 다음 배치에서 재시도. 5번 연속이면 숨은 차단으로 보고 멈춤 → 대기 |
| 리뷰 목록이 안 뜸 | 첫 번째는 재시도, 다음 실행에서도 그러면 `NO_REVIEWS` 확정 |
| 미매칭(`NOT_FOUND`) 10번 연속 | 이미 찾은 점포로 시험 검색. 그것도 실패하면 차단으로 보고 그 10곳을 PENDING으로 되돌리고 멈춤 |
| 예상 못 한 코드 오류 | 그 점포만 `ERROR`로 빼고 계속 |
| 연속 차단 8회 / 진전 없음 / 내 몫 완료 | 실행기 종료 |

점포 상태(`review_status`): `PENDING` 대기 · `COMPLETED` 수집 완료 · `NO_REVIEWS` 리뷰 없음 · `NOT_FOUND` 네이버에서 못 찾음 · `ERROR` 코드 오류(로그·`last_error` 확인).

## 7. 결과 넘기기

몫을 끝내면(또는 중간 공유 때):

```bash
.venv/bin/python export_reviews.py --out ~/Desktop/naver_reviews_<이름>_<날짜>.csv
```

CSV를 팀 드라이브에 올리고 김건우에게 알린다. 몫이 겹치지 않으므로 `store_id` 기준으로 그냥 이어 붙이면 된다. 정제(본문 끝 태그 분리, 방문일 변환, 오매칭 판정)는 합친 뒤 한 번에 한다.

`crawler.db`는 지우지 말고 보관한다(다시 내보내거나 재시도할 때 필요).

## 8. 알려진 한계 (분석할 때 주의)

- **매칭 검증이 없다.** 네이버 검색 결과 페이지에서 처음 나온 플레이스 링크를 고른다. 같은 이름의 다른 지점·광고 매장이 붙을 수 있고, 한 플레이스에 여러 점포가 붙는 경우가 있다(식사 기준 145건). 합친 뒤 주소 대조로 판정한다.
- **`naver_place_name`에 "일시적인 오류가 발생했습니다"가 자주 들어간다.** 속도를 위해 이미지를 막아서 생기는 대체 문구다. 이름은 매칭 검증에 쓰지 말 것.
- **점포당 리뷰 20건 상한.** 네이버 기본 정렬의 앞 20건이다. 리뷰 수를 인기 지표로 쓰지 않는다.
- **상권은 첫 상권만 저장된다.** 여러 상권에 걸친 점포(1.8만 곳)는 첫 상권으로만 들어가므로, 상권별 집계는 매핑 CSV를 `store_id`로 다시 붙여서 한다.
- 본문 끝에 "양이 많아요" 같은 추가 태그가 붙고, 일부 본문 앞에 "동영상" 같은 화면 문구가 섞인다. 정제 단계에서 분리한다.
