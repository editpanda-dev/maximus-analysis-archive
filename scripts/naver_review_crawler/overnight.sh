#!/bin/bash
# 무인 실행기: 내 몫의 PENDING 점포를 500곳씩 수집하고, 차단·연속 오류로 멈추면 쉬었다가 재개한다.
# 실행: nohup ./overnight.sh --purposes food --shard 0 --num-shards 3 > /dev/null 2>&1 &
#       (뒤의 인자는 run_crawler.py에 그대로 전달)
# 멈추기: kill $(cat logs/overnight.pid)
cd "$(dirname "$0")" || exit 1
PY="${PY:-.venv/bin/python}"
mkdir -p logs
LOG="logs/overnight_$(date +%Y%m%d_%H%M).log"
echo $$ > logs/overnight.pid
export PYTHONUNBUFFERED=1   # 로그를 줄 단위로 바로 기록

# 이 스크립트가 살아 있는 동안 잠자기 방지. 배터리에서는 시스템 잠자기를 못 막으니 충전기 연결, 덮개 열기.
command -v caffeinate >/dev/null && caffeinate -dimsu -w $$ &

COOL_START=1800   # 첫 차단 후 30분
COOL_MAX=7200     # 최대 2시간
MAX_BLOCKS=8      # 연속 차단이 이만큼이면 완전 중단
cool=$COOL_START
blocks=0

# 벽시계 기준 대기: 맥이 잠들었다 깨도 예정 시각이 지났으면 30초 안에 재개
wait_seconds() { local end=$(( $(date +%s) + $1 )); while [ "$(date +%s)" -lt "$end" ]; do sleep 30; done; }

while true; do
  echo "=== $(date '+%F %T') 배치 시작" >> "$LOG"
  out=$("$PY" run_crawler.py --limit 500 "$@" 2>&1 | tee -a "$LOG" | tail -15)

  if echo "$out" | grep -q "모든 점포 수집이 완료"; then
    echo "=== $(date '+%F %T') 내 몫 완료" >> "$LOG"; break
  elif echo "$out" | grep -q "조기 종료"; then
    blocks=$((blocks + 1))
    if [ "$blocks" -ge "$MAX_BLOCKS" ]; then
      echo "=== $(date '+%F %T') 연속 차단 ${blocks}회 → 완전 중단" >> "$LOG"; break
    fi
    echo "=== $(date '+%F %T') 차단/연속오류 ${blocks}회째 → ${cool}초 대기" >> "$LOG"
    wait_seconds "$cool"
    cool=$((cool * 2)); [ "$cool" -gt "$COOL_MAX" ] && cool=$COOL_MAX
  elif echo "$out" | grep -q "처리 점포: 0 /"; then
    # 차단도 아닌데 진전이 없음 (남은 점포가 전부 재시도 대기 등) → 무한 반복 방지
    echo "=== $(date '+%F %T') 진전 없음 → 중단" >> "$LOG"; break
  elif ! echo "$out" | grep -q "자율 실행 보고"; then
    # 실행기가 보고 없이 끝남 (설치 문제·DB 오류 등)
    echo "=== $(date '+%F %T') 실행기 비정상 종료 → 중단 (로그 확인)" >> "$LOG"; break
  else
    blocks=0; cool=$COOL_START
    wait_seconds 240   # 배치 사이 4분 휴식
  fi
done
echo "=== $(date '+%F %T') 종료" >> "$LOG"
rm -f logs/overnight.pid
