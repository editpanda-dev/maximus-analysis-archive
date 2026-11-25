"""네이버 카페 리뷰 정리 (2026-11-23): 식사판(build_naver_reviews.py)과 같은 매칭 판정·정제를 카페 DB에 돌린다.

카페는 crawler_other.db(purpose='카페')에 있다. 같은 DB의 공부·여가문화·쇼핑은 아직 수집 중이라 카페만 꺼낸다.
판정·정제 코드는 식사판 그대로 쓴다(judge_naver_match, clean_naver_dining_reviews). 정제 결과 파일 이름만 cafe_*로 바꾼다.
실행: ~/.venvs/maximus/bin/python 분석/build_naver_reviews_cafe.py
출력: 데이터/가공/naver_reviews_cafe/ store_match_judgment.csv, all_reviews_raw.csv, cafe_reviews_clean.csv, cafe_reviews_excluded.csv
"""
import sqlite3
from pathlib import Path

import pandas as pd

import clean_naver_dining_reviews
import judge_naver_match

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "수집/naver-review-crawler/crawler_other.db"
SNAP = ROOT / "데이터/캐시/naver_reviews/crawler_other_snapshot.db"
OUT_DIR = ROOT / "데이터/가공/naver_reviews_cafe"


def main():
    SNAP.parent.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(f"file:{DB}?mode=ro", uri=True), sqlite3.connect(SNAP)
    src.backup(dst)
    src.close()
    dst.close()

    # 판정은 카페 점포만 남긴 사본에서 (같은 플레이스 겹침 판정이 다른 목적 점포와 섞이지 않게)
    con = sqlite3.connect(SNAP)
    con.execute("DELETE FROM excel_dining_stores WHERE purpose != '카페'")
    con.commit()
    con.close()
    judge_naver_match.OUT = OUT_DIR / "store_match_judgment.csv"
    judge_naver_match.main(SNAP)

    con = sqlite3.connect(f"file:{SNAP}?mode=ro", uri=True)
    raw = pd.read_sql(
        """SELECT r.id AS review_id, r.store_id, s.store_name, s.area_code, s.area_name, s.address, s.category_small,
                  r.place_id, s.naver_place_name, s.naver_category, s.naver_review_total, s.naver_review_score,
                  r.author_name, r.rating, r.visit_date, r.visit_count, r.keywords, r.review_text, r.collected_at
           FROM reviews r JOIN excel_dining_stores s ON r.store_id = s.store_id ORDER BY r.id""", con)
    con.close()
    raw_path = OUT_DIR / "all_reviews_raw.csv"
    raw.to_csv(raw_path, index=False, encoding="utf-8-sig")
    print(f"카페 리뷰 추출 {len(raw)}행")

    clean_naver_dining_reviews.main(raw_path, OUT_DIR)
    for a, b in [("dining_reviews_clean.csv", "cafe_reviews_clean.csv"), ("dining_reviews_excluded.csv", "cafe_reviews_excluded.csv")]:
        (OUT_DIR / a).replace(OUT_DIR / b)
    d = pd.read_csv(OUT_DIR / "cafe_reviews_clean.csv", usecols=["store_id"], encoding="utf-8-sig")
    print(f"카페 정제 {len(d)}행 · 가게 {d.store_id.nunique()}")


if __name__ == "__main__":
    main()
