#!/bin/bash
# 무인 실행기: 내 몫의 PENDING 점포를 500곳씩 수집하고, 차단·연속 오류로 멈추면 쉬었다가 재개한다.
#  - 인터넷이 끊기면(와이파이 이동 등) 차단으로 세지 않고, 다시 연결될 때까지 기다렸다가 이어간다
#  - 맥 덮개를 닫아 잠들었다 깨서 난 타임아웃도 차단으로 세지 않고 바로 이어간다
#  - 배치마다 먼저 가게 정보(네이버 이름·주소)가 빠진 점포를 backfill_place_meta.py로 채운다
# 실행: nohup ./overnight.sh --purposes food --shard 0 --num-shards 3 > /dev/null 2>&1 &
#       (뒤의 인자는 run_crawler.py에 그대로 전달)
# 멈추기: kill $(cat logs/overnight.pid)
cd "$(dirname "$0")" || exit 1
PY="${PY:-.venv/bin/python}"
mkdir -p logs

# 이미 다른 실행기가 돌고 있으면 그대로 둔다 (중복 실행 = 요청 2배 = 차단 위험)
old=$(cat logs/overnight.pid 2>/dev/null)
if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
  echo "이미 실행 중 (pid $old)"; exit 0
fi
echo $$ > logs/overnight.pid
trap 'rm -f logs/overnight.pid' EXIT
LOG="logs/overnight_$(date +%Y%m%d_%H%M).log"
export PYTHONUNBUFFERED=1   # 로그를 줄 단위로 바로 기록

# 이 스크립트가 살아 있는 동안 저절로 잠들지 않게 (화면은 꺼져도 됨). 덮개를 닫으면 배터리에서는 잠든다.
command -v caffeinate >/dev/null && caffeinate -is -w $$ &

COOL_START=1800   # 첫 차단 후 30분
COOL_MAX=7200     # 최대 2시간
MAX_BLOCKS=8      # 연속 차단이 이만큼이면 완전 중단
cool=$COOL_START
blocks=0
# 차단이 아니라 인터넷이 끊겨서 난 오류
OFFLINE_RE="ERR_INTERNET_DISCONNECTED|ERR_NAME_NOT_RESOLVED|ERR_NETWORK_CHANGED|ERR_ADDRESS_UNREACHABLE|ERR_NETWORK_IO_SUSPENDED"

say() { echo "=== $(date '+%F %T') $*" >> "$LOG"; }
# 벽시계 기준 대기: 맥이 잠들었다 깨도 예정 시각이 지났으면 20초 안에 재개
wait_seconds() { local end=$(( $(date +%s) + $1 )); while [ "$(date +%s)" -lt "$end" ]; do sleep 20; done; }
# 이번 배치 도중 맥이 잠들었다 깼는지 (맥 전용, 다른 OS에서는 늘 아니라고 답함)
woke_since() {
  local w; w=$(sysctl -n kern.waketime 2>/dev/null | sed -nE 's/^\{ sec = ([0-9]+),.*/\1/p')
  [ -n "$w" ] && [ "$w" -gt "$1" ]
}
naver_up() { [ "$(curl -s -o /dev/null -w '%{http_code}' -m 10 'https://m.search.naver.com/search.naver?query=test')" = 200 ]; }
wait_online() {
  naver_up && return
  say "인터넷 대기 (네이버 접속 안 됨)"
  until naver_up; do sleep 60; done
  say "인터넷 연결됨 → 재개"
  sleep 30   # 막 붙은 직후 불안정 구간 넘기기
}

say "실행기 시작"
while true; do
  wait_online
  batch_start=$(date +%s)
  out=$("$PY" backfill_place_meta.py --limit 500 2>&1 | tee -a "$LOG" | tail -15)
  if ! echo "$out" | grep -q "채울 점포 없음"; then
    job="채우기"
  else
    job="수집"; say "배치 시작"
    out=$("$PY" run_crawler.py --limit 500 "$@" 2>&1 | tee -a "$LOG" | tail -15)
  fi

  if [ "$job" = 수집 ] && echo "$out" | grep -q "모든 점포 수집이 완료"; then
    say "내 몫 완료"; break
  elif ! echo "$out" | grep -q "🏁"; then
    # 실행기가 보고 없이 끝남 (설치 문제·DB 오류 등)
    say "${job} 비정상 종료 → 중단 (로그 확인)"; break
  elif echo "$out" | grep -q "조기 종료" && echo "$out" | grep -qE "$OFFLINE_RE"; then
    say "${job} 중 인터넷 끊김 → 연결 대기 (차단 아님)"
  elif echo "$out" | grep -q "조기 종료" && woke_since "$batch_start"; then
    say "${job} 중 맥이 잠들었다 깸 → 바로 재개 (차단 아님)"
  elif echo "$out" | grep -q "조기 종료"; then
    blocks=$((blocks + 1))
    if [ "$blocks" -ge "$MAX_BLOCKS" ]; then
      say "연속 차단 ${blocks}회 → 완전 중단"; break
    fi
    say "차단/연속오류 ${blocks}회째 → ${cool}초 대기"
    wait_seconds "$cool"
    cool=$((cool * 2)); [ "$cool" -gt "$COOL_MAX" ] && cool=$COOL_MAX
  elif [ "$job" = 수집 ] && echo "$out" | grep -q "처리 점포: 0 /"; then
    # 차단도 아닌데 진전이 없음 (남은 점포가 전부 재시도 대기 등) → 무한 반복 방지
    say "진전 없음 → 중단"; break
  else
    blocks=0; cool=$COOL_START
    wait_seconds 240   # 배치 사이 4분 휴식
  fi
done
say "종료"
