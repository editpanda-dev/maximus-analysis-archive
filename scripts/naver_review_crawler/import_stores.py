"""상권–점포 매핑(data/processed/area_store_mapping)에서 수집 대상 점포를 crawler DB에 적재.

실행 (이 폴더에서):
    python import_stores.py                      # 전체 목적, 기본 경로
    python import_stores.py --purposes food,cafe # 일부 목적만

- 매핑은 상권–점포 쌍(237,718행)이지만 수집은 점포 단위(219,859곳)라 store_id 기준으로 한 번만 넣는다.
  area_code/area_name은 첫 번째 상권만 남으므로, 상권별 집계는 수집 후 매핑 CSV를 다시 붙여서 한다.
- purpose는 purposes 배열의 첫 값(현재 데이터는 점포당 최대 1개), 없으면 none.
- 이미 있는 점포는 건드리지 않는다(INSERT OR IGNORE). 진행 상태가 보존되므로 여러 번 실행해도 안전하다.
"""
import argparse
import csv
import io
import json
import sqlite3
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE.parents[1] / "data/processed/area_store_mapping/area_store_20260630.zip"
DEFAULT_DB = HERE / "crawler.db"
# 적재 순서 = 수집 순서(rowid). 분석에 먼저 쓰는 목적부터.
PURPOSE_ORDER = ["food", "cafe", "study", "leisure", "shopping", "none"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS excel_dining_stores (
    store_id TEXT PRIMARY KEY,
    area_code TEXT, area_name TEXT, store_name TEXT, address TEXT,
    category_large TEXT, category_mid TEXT, category_small TEXT,
    lon REAL, lat REAL,
    search_query_used TEXT,
    search_status TEXT DEFAULT 'PENDING',
    naver_place_id TEXT, naver_place_name TEXT,
    review_status TEXT DEFAULT 'PENDING',
    review_count_collected INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    purpose TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL, place_id TEXT NOT NULL,
    author_name TEXT, rating TEXT, review_text TEXT,
    visit_date TEXT, visit_count TEXT, keywords TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_eds_status ON excel_dining_stores(review_status);
CREATE INDEX IF NOT EXISTS idx_reviews_store_id ON reviews(store_id);
"""
# 테이블 이름 excel_dining_stores는 엑셀 식사 시트로 시작한 기존 DB와 호환하려고 유지한다.


def read_rows(source: Path):
    if source.suffix == ".zip":
        with zipfile.ZipFile(source) as z:
            name = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(name) as f:
                yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
    else:
        with open(source, encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description="수집 대상 점포 적재")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="area_store_*.zip 또는 .csv")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--purposes", default=",".join(PURPOSE_ORDER), help="쉼표 구분: " + ",".join(PURPOSE_ORDER))
    args = ap.parse_args()
    wanted = [p.strip() for p in args.purposes.split(",") if p.strip()]
    unknown = set(wanted) - set(PURPOSE_ORDER)
    if unknown:
        raise SystemExit(f"알 수 없는 목적: {unknown}")

    by_purpose = {p: [] for p in PURPOSE_ORDER}
    seen = set()
    for r in read_rows(args.source):
        sid = r["place_id"]
        if sid in seen:
            continue  # 복수 상권 소속 점포: 첫 상권만
        seen.add(sid)
        tags = json.loads(r["purposes"] or "[]")
        purpose = tags[0] if tags else "none"
        if purpose not in by_purpose:
            purpose = "none"
        cats = [c.strip() for c in (r.get("category_name") or "").split(">")] + ["", "", ""]
        by_purpose[purpose].append((
            sid, r["area_code"], r["area_name"], r["place_name"], r["address"],
            cats[0], cats[1], cats[2], to_float(r.get("longitude")), to_float(r.get("latitude")), purpose,
        ))

    conn = sqlite3.connect(args.db)
    conn.executescript(SCHEMA)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(excel_dining_stores)")]
    if "purpose" not in cols:  # 엑셀로 만든 예전 DB
        conn.execute("ALTER TABLE excel_dining_stores ADD COLUMN purpose TEXT")

    for p in PURPOSE_ORDER:
        if p not in wanted:
            continue
        rows = by_purpose[p]
        before = conn.total_changes
        conn.executemany("""
            INSERT OR IGNORE INTO excel_dining_stores (
                store_id, area_code, area_name, store_name, address,
                category_large, category_mid, category_small, lon, lat, purpose
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        added = conn.total_changes - before
        # 예전 DB에서 purpose가 비어 있던 점포에 목적 채우기 (진행 상태는 그대로)
        conn.executemany("UPDATE excel_dining_stores SET purpose = ? WHERE store_id = ? AND purpose IS NULL",
                         [(p, row[0]) for row in rows])
        conn.commit()
        print(f"{p:9s} 점포 {len(rows):6,d}곳 중 새로 추가 {added:6,d}곳")

    print("목적별 상태:")
    for p, st, n in conn.execute(
            "SELECT purpose, review_status, count(*) FROM excel_dining_stores GROUP BY 1, 2 ORDER BY 1, 2"):
        print(f"  {p or '(없음)':9s} {st:11s} {n:,}")
    conn.close()


if __name__ == "__main__":
    main()
