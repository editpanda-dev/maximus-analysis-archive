"""
이미 수집한 점포의 네이버 가게 정보(이름·업종·주소·리뷰 총수) 채우기.
예전 실행은 검색 결과 링크 글자를 가게명으로 저장해 '일시적인 오류…'·빈 값이 대부분이다.
플레이스 페이지를 한 번씩 열어 read_place_meta로 다시 읽는다. 리뷰는 건드리지 않는다.

  python backfill_place_meta.py --limit 500 [--db crawler.db]
같은 IP에서 수집기(overnight.sh)와 동시에 돌리면 요청이 두 배가 되니, 수집이 끝났거나 멈췄을 때 돌린다.
"""
import argparse
import sqlite3
import time
from pathlib import Path

import run_crawler
from run_crawler import TRANSIENT_STREAK_LIMIT, ensure_meta_columns, update_store
from ultra_fast_crawler import CrawlBlocked, CrawlTransient, UltraFastCrawler


def targets(limit):
    conn = sqlite3.connect(run_crawler.DB_PATH)
    rows = conn.execute("""
        SELECT store_id, naver_place_id FROM excel_dining_stores
        WHERE search_status = 'MATCHED' AND naver_place_id IS NOT NULL
          AND naver_road_address IS NULL AND review_status IN ('COMPLETED', 'NO_REVIEWS')
        ORDER BY rowid LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--db", type=Path, default=run_crawler.DB_PATH, help="SQLite DB 경로 (기본: 이 폴더의 crawler.db)")
    args = ap.parse_args()
    run_crawler.DB_PATH = args.db  # update_store도 이 경로를 쓴다
    ensure_meta_columns()

    rows = targets(args.limit)
    print(f"대상 {len(rows)}곳")
    if not rows:
        print("🎉 채울 점포 없음")
        return

    crawler = UltraFastCrawler(headless=True)
    crawler.start()
    done = missing = 0
    streak = 0
    stop_reason = ""
    try:
        for i, (store_id, place_id) in enumerate(rows, start=1):
            if i > 1 and i % 30 == 0:
                crawler._new_context()
                crawler.random_sleep(3.0, 5.0)
            if i > 1 and i % 100 == 0:
                time.sleep(25.0)
            try:
                crawler._goto(f"https://m.place.naver.com/restaurant/{place_id}/review/visitor", timeout=12000)
                meta = crawler.read_place_meta(place_id)
            except CrawlBlocked as e:
                stop_reason = f"네이버 차단 감지: {e}"
                break
            except CrawlTransient as e:
                streak += 1
                if streak >= TRANSIENT_STREAK_LIMIT:
                    stop_reason = f"일시 오류 {streak}회 연속: {e}"
                    break
                crawler.random_sleep(1.8, 3.2)
                continue
            streak = 0
            if meta.get("naver_place_name"):
                update_store(store_id, **meta)
                done += 1
            else:
                # 페이지 데이터가 없으면 빈 문자열로 표시해 다음 실행에서 다시 시도하지 않는다
                update_store(store_id, naver_road_address="")
                missing += 1
            crawler.random_sleep(1.8, 3.2)
    finally:
        crawler.stop()
        if stop_reason:
            print(f"🛑 조기 종료: {stop_reason}")
        print(f"🏁 채움 {done}곳 · 정보 없음 {missing}곳 / 대상 {len(rows)}곳")


if __name__ == "__main__":
    main()
