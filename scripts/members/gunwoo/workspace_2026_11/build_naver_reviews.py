"""네이버 식사 리뷰 정리 한 번에: DB 사본 → 매칭 판정 → 리뷰 추출 → 정제 → 공유본 CSV → 상권에 다시 붙이기.

크롤러가 도는 중에도 돌려도 된다 (DB를 사본으로 떠서 읽기만 함).
실행:
    ~/.venvs/maximus/bin/python 분석/build_naver_reviews.py
출력:
    데이터/가공/naver_reviews/  store_match_judgment.csv, all_reviews_raw.csv, dining_reviews_clean.csv, ...
    데이터/가공/naver_reviews/막시무스_리뷰_모음.csv  (공유용 열만)
    데이터/가공/naver_reviews/dining_store_by_area.csv   상권×식사 점포 (한 점포가 여러 상권이면 상권마다 한 행)
    데이터/가공/naver_reviews/area_dining_review_summary.csv  상권별 요약
상권은 크롤러 DB에 첫 상권만 들어 있어서, 매핑(데이터/원천/area_store_20260630.zip)에서 다시 붙인다.
"""
import sqlite3
from pathlib import Path

import pandas as pd

import clean_naver_dining_reviews
import judge_naver_match

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "수집/naver-review-crawler/crawler.db"
SNAP = ROOT / "데이터/캐시/naver_reviews/crawler_snapshot.db"
OUT_DIR = ROOT / "데이터/가공/naver_reviews"
SHARE_CSV = OUT_DIR / "막시무스_리뷰_모음.csv"
MAPPING = ROOT / "데이터/원천/area_store_20260630.zip"
SHARE_COLS = [
    "review_id", "store_id", "store_name", "area_code", "area_name", "address", "category_small", "place_id",
    "naver_place_name", "naver_category", "naver_review_total", "naver_review_score", "match_status",
    # author_name은 공유본에서 뺀다 (설계 6장: 닉네임 미보관)
    "rating", "visit_date", "visit_count", "keywords", "extra_tags", "review_text",
    "row_shifted", "place_shared", "collected_at",
]


def main():
    SNAP.parent.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(f"file:{DB}?mode=ro", uri=True), sqlite3.connect(SNAP)
    src.backup(dst)
    src.close()
    dst.close()

    judge_naver_match.main(SNAP)

    con = sqlite3.connect(f"file:{SNAP}?mode=ro", uri=True)
    raw = pd.read_sql(
        """SELECT r.id AS review_id, r.store_id, s.store_name, s.area_code, s.area_name, s.address, s.category_small,
                  r.place_id, s.naver_place_name, s.naver_category, s.naver_review_total, s.naver_review_score,
                  r.author_name, r.rating, r.visit_date, r.visit_count, r.keywords, r.review_text, r.collected_at
           FROM reviews r LEFT JOIN excel_dining_stores s ON r.store_id = s.store_id ORDER BY r.id""", con)
    raw_path = OUT_DIR / "all_reviews_raw.csv"
    raw.to_csv(raw_path, index=False, encoding="utf-8-sig")
    print(f"리뷰 추출 {len(raw)}행")

    clean_naver_dining_reviews.main(raw_path, OUT_DIR)

    d = pd.read_csv(OUT_DIR / "dining_reviews_clean.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    d[SHARE_COLS].to_csv(SHARE_CSV, index=False, encoding="utf-8-sig")
    print(f"공유본 저장 {SHARE_CSV} {d.shape[0]}행 · 가게 {d.store_id.nunique()} · 상권 {d.area_name.nunique()}")

    attach_areas(con, d)


def attach_areas(con, reviews):
    """매핑의 모든 상권–식사 점포 행에 수집 상태·매칭 판정·네이버 리뷰 수·수집 리뷰 요약을 붙인다."""
    m = pd.read_csv(MAPPING, dtype=str)
    m = m[m.purposes.str.contains("food", na=False)][["area_code", "area_name", "place_id", "place_name", "subcategory"]]
    m = m.rename(columns={"place_id": "store_id", "place_name": "store_name"})

    status = pd.read_sql("SELECT store_id, review_status FROM excel_dining_stores", con)
    judge = pd.read_csv(OUT_DIR / "store_match_judgment.csv", dtype={"store_id": str})
    judge = judge[["store_id", "naver_place_name", "match_status", "keep", "naver_review_total"]]
    reviews = reviews.assign(rating=pd.to_numeric(reviews.rating, errors="coerce"))
    per_store = reviews.groupby("store_id").agg(n_reviews=("review_id", "size"), mean_rating=("rating", "mean"),
                                                naver_review_score=("naver_review_score", "first")).reset_index()

    st = m.merge(status, on="store_id", how="left").merge(judge, on="store_id", how="left").merge(per_store, on="store_id", how="left")
    st["usable"] = st.keep.eq(True) & st.review_status.isin(["COMPLETED", "NO_REVIEWS"])
    st.drop(columns="keep").to_csv(OUT_DIR / "dining_store_by_area.csv", index=False, encoding="utf-8-sig")

    u = st[st.usable]
    g = st.groupby(["area_code", "area_name"])
    summary = pd.DataFrame({
        "food_stores": g.size(),
        "crawled": g.review_status.agg(lambda s: s.isin(["COMPLETED", "NO_REVIEWS", "NOT_FOUND"]).sum()),
        "usable_stores": g.usable.sum(),
    }).join(u.groupby(["area_code", "area_name"]).agg(
        naver_review_total_sum=("naver_review_total", "sum"),
        naver_review_total_median=("naver_review_total", "median"),
        collected_reviews=("n_reviews", "sum"),
        mean_rating_2026=("mean_rating", "mean"),
    )).reset_index()
    summary["crawl_coverage"] = (summary.crawled / summary.food_stores).round(3)
    summary.to_csv(OUT_DIR / "area_dining_review_summary.csv", index=False, encoding="utf-8-sig")
    done = summary[summary.crawl_coverage >= 0.999]
    print(f"상권 붙이기: 상권 {len(summary)}곳 · 식사 점포-상권 {len(st)}행 · 쓸 수 있는 점포 {u.store_id.nunique()}곳 "
          f"· 수집 끝난 상권 {len(done)}곳")


if __name__ == "__main__":
    main()
