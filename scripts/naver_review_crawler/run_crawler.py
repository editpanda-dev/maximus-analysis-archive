"""
네이버 플레이스 리뷰 수집 실행기 (run_crawler.py)

PENDING 점포를 --limit 개만큼 처리한다. 사람별 분담은 --purposes(목적)와
--shard/--num-shards(점포 ID 해시로 나눈 몫)로 겹치지 않게 나눈다. 자세한 사용법은 HANDOFF.md.
"""
import argparse
import re
import sqlite3
import sys
import time
import zlib
from pathlib import Path

from ultra_fast_crawler import REVIEW_LIST_TIMEOUT, CrawlBlocked, CrawlTransient, UltraFastCrawler

DB_PATH = Path(__file__).resolve().parent / "crawler.db"
DEFAULT_BATCH_SIZE = 500
MAX_REVIEWS_PER_STORE = 20
# 연속 NOT_FOUND가 이만큼 쌓이면 이미 찾은 점포로 검색이 되는지(카나리) 확인한다.
# 카나리도 실패하면 차단으로 보고 그 연속 구간을 PENDING으로 되돌린 뒤 멈춘다.
NOT_FOUND_STREAK_LIMIT = 10
# 일시 오류가 이만큼 연속되면 숨은 차단으로 보고 멈춘다.
TRANSIENT_STREAK_LIMIT = 5


def update_store(store_id: str, **fields):
    conn = sqlite3.connect(DB_PATH)
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE excel_dining_stores SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE store_id = ?",
        (*fields.values(), store_id),
    )
    conn.commit()
    conn.close()


# 리뷰 페이지에서 읽는 네이버 측 가게 정보 (매칭 검증용). 예전 DB에는 없어서 실행 시 추가한다.
META_COLUMNS = {
    "naver_category": "TEXT", "naver_road_address": "TEXT", "naver_address": "TEXT",
    "naver_review_total": "INTEGER", "naver_review_score": "REAL",
}


def ensure_meta_columns():
    conn = sqlite3.connect(DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(excel_dining_stores)")}
    for name, typ in META_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE excel_dining_stores ADD COLUMN {name} {typ}")
    conn.commit()
    conn.close()


def get_canary_store():
    """이미 정상 매칭된 점포 하나 (STEP_1 검색어로 찾았고 이름이 정상인 것)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT store_name, area_name FROM excel_dining_stores
        WHERE search_status = 'MATCHED' AND search_query_used LIKE 'STEP_1:%'
          AND naver_place_name NOT IN ('', '일시적인 오류가 발생했습니다')
        ORDER BY rowid LIMIT 1
    """).fetchone()
    conn.close()
    return dict(row) if row else None


def canary_ok(crawler) -> bool:
    store = get_canary_store()
    if store is None:
        return True  # 비교 기준이 없으면 판단 보류
    name = re.sub(r"[()]", " ", store["store_name"]).strip()
    area = (store["area_name"] or "").split("(")[0].strip()
    try:
        return crawler.find_place_id({"name": name, "area_name": area}) is not None
    except (CrawlBlocked, CrawlTransient):
        return False


def shard_of(store_id: str, num_shards: int) -> int:
    """점포 ID의 고정 해시 몫. 누구 컴퓨터에서 계산해도 같은 값이 나온다."""
    return zlib.crc32(store_id.encode("utf-8")) % num_shards


def get_pending_stores(limit: int, purposes=None, shard: int = 0, num_shards: int = 1):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.create_function("shard_of", 2, shard_of, deterministic=True)
    sql = "SELECT * FROM excel_dining_stores WHERE review_status = 'PENDING'"
    params = []
    if purposes:
        sql += f" AND purpose IN ({','.join('?' * len(purposes))})"
        params += purposes
    if num_shards > 1:
        sql += " AND shard_of(store_id, ?) = ?"
        params += [num_shards, shard]
    sql += " ORDER BY rowid ASC LIMIT ?"
    params.append(limit)
    stores = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return stores


def main():
    global DB_PATH
    parser = argparse.ArgumentParser(description="네이버 플레이스 리뷰 수집 실행기")
    parser.add_argument("--limit", type=int, default=DEFAULT_BATCH_SIZE, help="처리할 점포 수")
    parser.add_argument("--max-reviews", type=int, default=MAX_REVIEWS_PER_STORE, help="점포당 수집 리뷰 수")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite DB 경로 (기본: 이 폴더의 crawler.db)")
    parser.add_argument("--purposes", default="", help="쉼표 구분 목적 필터: food,cafe,shopping,study,leisure,none")
    parser.add_argument("--shard", type=int, default=0, help="내 담당 몫 번호 (0부터)")
    parser.add_argument("--num-shards", type=int, default=1, help="전체 담당자 수")
    args = parser.parse_args()
    if not 0 <= args.shard < args.num_shards:
        sys.exit("--shard 는 0 이상 --num-shards 미만이어야 합니다")
    DB_PATH = args.db
    ensure_meta_columns()
    purposes = [p.strip() for p in args.purposes.split(",") if p.strip()]

    stores = get_pending_stores(args.limit, purposes, args.shard, args.num_shards)
    total = len(stores)
    print("=" * 75)
    print(f"🌙 리뷰 수집 시작: {total}곳 (목적 {','.join(purposes) or '전체'}, 몫 {args.shard}/{args.num_shards}, DB {DB_PATH.name})")
    print("=" * 75)

    if total == 0:
        print("🎉 모든 점포 수집이 완료되었습니다!")
        return

    crawler = UltraFastCrawler(headless=True)
    crawler.start()

    success_count = 0
    not_found_count = 0
    no_reviews_count = 0
    retry_count = 0
    total_reviews = 0
    not_found_streak = []  # 연속 NOT_FOUND 점포 ID
    transient_streak = 0
    stop_reason = ""
    start_time = time.time()

    try:
        for idx, s in enumerate(stores, start=1):
            s_id = s["store_id"]
            name = s["store_name"]
            area = s["area_name"]
            item_start = time.time()

            # 30개 점포마다 세션 클린업
            if idx > 1 and idx % 30 == 0:
                print("\n🔄 [자율 관리] 브라우저 세션 클린업 및 메모리 정리...")
                crawler._new_context()
                crawler.random_sleep(3.0, 5.0)

            # 100개 점포마다 25초 휴식 (차단 방지 쿨다운)
            if idx > 1 and idx % 100 == 0:
                print("☕ [자율 쿨다운] 차단 방지를 위해 25초간 휴식합니다...")
                time.sleep(25.0)

            try:
                result = process_store(crawler, s, args.max_reviews)
            except CrawlBlocked as e:
                stop_reason = f"네이버 차단 감지: {e}"
                update_store(s_id, last_error=f"blocked: {e}"[:300])
                break
            except CrawlTransient as e:
                msg = str(e)
                if msg == REVIEW_LIST_TIMEOUT and s.get("last_error") == REVIEW_LIST_TIMEOUT:
                    # 두 번째 실행에서도 리뷰 목록이 안 뜸 → 리뷰 없음으로 확정
                    update_store(s_id, review_status="NO_REVIEWS", review_count_collected=0, last_error=msg)
                    no_reviews_count += 1
                    transient_streak = 0
                    print(f"[{idx:4d}/{total}] 🏬 {name[:16]:16s} | {area[:10]:10s} ➔ ℹ️ [리뷰 없음 확정(2회 시간초과)]")
                else:
                    update_store(s_id, last_error=msg[:300])  # 상태는 PENDING 유지 → 다음 실행에서 재시도
                    retry_count += 1
                    transient_streak += 1
                    print(f"[{idx:4d}/{total}] 🏬 {name[:16]:16s} | {area[:10]:10s} ➔ ⏳ [일시 오류, 재시도 대기] {msg[:60]}")
                    if transient_streak >= TRANSIENT_STREAK_LIMIT:
                        stop_reason = f"일시 오류 {transient_streak}회 연속 (숨은 차단 의심)"
                        break
                crawler.random_sleep(1.8, 3.2)
                continue
            except Exception as e:
                # 파싱 버그 등 예상 못 한 오류: 같은 점포에서 매번 멈추지 않도록 ERROR로 빼고 진행
                update_store(s_id, review_status="ERROR", last_error=f"unexpected: {type(e).__name__}: {e}"[:300])
                print(f"[{idx:4d}/{total}] 🏬 {name[:16]:16s} | {area[:10]:10s} ➔ ⚠️ [예상 못 한 오류, 건너뜀] {type(e).__name__}")
                crawler.random_sleep(1.8, 3.2)
                continue

            transient_streak = 0
            status, n_reviews = result
            if status == "NOT_FOUND":
                not_found_count += 1
                not_found_streak.append(s_id)
                if len(not_found_streak) >= NOT_FOUND_STREAK_LIMIT:
                    if canary_ok(crawler):
                        not_found_streak = []
                    else:
                        for sid in not_found_streak:
                            update_store(sid, search_status="PENDING", review_status="PENDING",
                                         last_error="reverted: not_found_streak_canary_failed")
                        not_found_count -= len(not_found_streak)
                        stop_reason = f"NOT_FOUND {len(not_found_streak)}회 연속 + 카나리 검색 실패 → 차단으로 판단, 해당 점포 PENDING 복구"
                        break
            else:
                not_found_streak = []
                if status == "COMPLETED":
                    success_count += 1
                    total_reviews += n_reviews
                else:
                    no_reviews_count += 1

            elapsed_item = time.time() - item_start
            status_txt = {"NOT_FOUND": "❌ [미매칭]", "NO_REVIEWS": "ℹ️ [리뷰 없음]"}.get(status, f"✨ [수집 {n_reviews:2d}건]")
            print(f"[{idx:4d}/{total}] 🏬 {name[:16]:16s} | {area[:10]:10s} ➔ {status_txt} ({elapsed_item:.1f}s)")

            # 인간 모방 안전 지연 (차단 방지)
            crawler.random_sleep(1.8, 3.2)

    except KeyboardInterrupt:
        print("\n🛑 중단되었습니다. (현재까지 수집 데이터 100% 안전 보존)")
    except Exception as e:
        print(f"\n🚨 에러 발생: {e}")
    finally:
        crawler.stop()
        total_time = time.time() - start_time
        processed = success_count + not_found_count + no_reviews_count
        print("\n" + "=" * 75)
        print("🏁 [자율 실행 보고]")
        if stop_reason:
            print(f"🛑 조기 종료: {stop_reason}")
        print(f"⏱️ 총 소요 시간: {total_time:.1f}초 ({total_time/60:.1f}분)")
        print(f"🏬 처리 점포: {processed} / {total}곳 (재시도 대기 {retry_count}곳)")
        print(f"✅ 리뷰 수집 성공: {success_count}곳")
        print(f"💬 총 수집 리뷰: {total_reviews:,}건")
        print("=" * 75)


def process_store(crawler, s, max_reviews):
    """점포 1곳 처리. ('COMPLETED'|'NO_REVIEWS'|'NOT_FOUND', 리뷰 수) 반환.
    CrawlBlocked/CrawlTransient는 점포 상태를 바꾸지 않고 호출자로 올린다."""
    s_id = s["store_id"]
    name = s["store_name"]
    area = s["area_name"]
    addr = s["address"]

    # 1단계: Place ID 탐색 (이전 실행에서 찾아둔 ID가 있으면 재사용)
    place_id = s.get("naver_place_id")
    if not place_id:
        clean_name = re.sub(r"[()]", " ", name).strip()
        clean_area = area.split("(")[0].strip() if area else ""
        # 주소에서 구/동 추출
        addr_match = re.search(r"([가-힣]+구)\s+([가-힣\d]+(?:로|길|동))", addr)
        store_query_dict = {
            "name": clean_name,
            "area_name": clean_area,
            "area_district": addr_match.group(1) if addr_match else "",
            "area_admin": addr_match.group(2) if addr_match else "",
        }
        found = crawler.find_place_id(store_query_dict)
        if not found:
            update_store(s_id, search_status="NOT_FOUND", review_status="NOT_FOUND", last_error=None)
            return "NOT_FOUND", 0

        place_id, place_name, used_query = found
        update_store(s_id, search_status="MATCHED", naver_place_id=place_id,
                     naver_place_name=place_name, search_query_used=used_query)

    # 2단계: 리뷰 본문 수집
    reviews = crawler.scrape_reviews(s_id, place_id, max_reviews=max_reviews)
    try:
        meta = crawler.read_place_meta(place_id)
    except Exception:
        meta = {}  # 가게 정보는 검증용 부가 정보라 실패해도 리뷰 저장은 진행
    if meta.get("naver_place_name"):
        update_store(s_id, **meta)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for r in reviews:
        c.execute("""
            INSERT INTO reviews (
                store_id, place_id, author_name, rating,
                review_text, visit_date, visit_count, keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["store_id"], r["place_id"], r.get("author_name"),
            r.get("rating"), r.get("review_text"), r.get("visit_date"),
            r.get("visit_count"), r.get("keywords")
        ))
    status = "COMPLETED" if reviews else "NO_REVIEWS"
    c.execute("""
        UPDATE excel_dining_stores
        SET review_status = ?, review_count_collected = ?, last_error = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE store_id = ?
    """, (status, len(reviews), s_id))
    conn.commit()
    conn.close()
    return status, len(reviews)


if __name__ == "__main__":
    main()
