"""crawler DB의 리뷰를 CSV로 내보내기 (점포 정보 포함).

실행: python export_reviews.py --out ~/Desktop/naver_reviews_<이름>.csv
- 수집 대상 테이블(excel_dining_stores)에 있는 점포의 리뷰만 내보낸다(옛 시험 수집 테이블 리뷰 제외).
- 원본 그대로다. 정제(태그 분리·날짜 변환·오매칭 판정)는 분석 단계에서 한다.
- 리뷰에는 작성자 닉네임이 들어 있으므로 공개 저장소에 커밋하지 않는다.
"""
import argparse
import csv
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=HERE / "crawler.db")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(excel_dining_stores)")]
    purpose = "s.purpose" if "purpose" in cols else "NULL"
    cur = conn.execute(f"""
        SELECT r.id AS review_id, r.store_id, {purpose} AS purpose, s.store_name, s.area_code, s.area_name,
               s.address, s.category_small, r.place_id, s.naver_place_name, r.author_name, r.rating,
               r.visit_date, r.visit_count, r.keywords, r.review_text, r.collected_at
        FROM reviews r JOIN excel_dining_stores s ON r.store_id = s.store_id
        ORDER BY r.id
    """)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([d[0] for d in cur.description])
        n = 0
        for row in cur:
            w.writerow(row)
            n += 1
    conn.close()
    print(f"리뷰 {n:,}건 → {args.out}")


if __name__ == "__main__":
    main()
