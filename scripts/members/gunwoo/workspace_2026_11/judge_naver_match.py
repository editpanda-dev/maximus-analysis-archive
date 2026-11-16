"""우리 가게(소상공인 데이터) ↔ 네이버 플레이스 매칭이 맞는지 가게마다 판정.

크롤러가 플레이스 페이지에서 읽어 둔 네이버 이름·도로명주소(naver_* 열)를 우리 이름·주소와 비교한다.
실행:
    ~/.venvs/maximus/bin/python 분석/judge_naver_match.py [crawler.db]
출력: 데이터/가공/naver_reviews/store_match_judgment.csv  (clean_naver_dining_reviews.py가 읽어 틀린 매칭 리뷰를 뺀다)

가게별 match_status (keep = 리뷰를 쓸지):
  address    도로명주소(구+도로+번호) 일치                          keep
  name       같은 구 안에서 주소는 다르지만 이름이 같음(유사도 0.8+, 짧은 쪽이 긴 쪽의 절반 이상이면 포함도 인정)
             — 이전·주소 표기 차이                                    keep
  near       같은 구·같은 도로, 건물번호 차이 4 이내, 이름 유사도 0.6+     keep
  no_meta    네이버 정보를 못 읽어 판정 불가                          keep
  mismatch   주소도 이름도 안 맞음 → 다른 가게에 잘못 붙음                 drop
  shared_loser  여러 가게가 같은 플레이스에 붙었는데 더 맞는 가게가 따로 있음   drop
"""
import re
import sqlite3
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "수집/naver-review-crawler/crawler.db"
OUT = ROOT / "데이터/가공/naver_reviews/store_match_judgment.csv"
NAME_SIM_OK = 0.8
NAME_SIM_NEAR = 0.6
NEAR_NUM_GAP = 4
RANK = {"address": 3, "name": 2, "near": 1, "no_meta": 0, "mismatch": -1}


def norm_name(s):
    s = re.sub(r"\(.*?\)", "", str(s or "")).lower()
    return re.sub(r"[^가-힣a-z0-9]", "", s)


def addr_key(s):
    """'서울특별시 종로구 종로40가길 5 1층' -> ('종로구', '종로40가길', '5')"""
    m = re.search(r"(\S+구)\s+(\S+(?:로|길))\s*(\d+(?:-\d+)?)", str(s or ""))
    return m.groups() if m else None


def name_sim(a, b):
    a, b = norm_name(a), norm_name(b)
    if not a or not b:
        return 0.0
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 2 and len(short) * 2 >= len(long_) and short in long_:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def gu(s):
    m = re.search(r"(\S+구)\s", str(s or ""))
    return m.group(1) if m else None


def bldg_no(k):
    return int(k[2].split("-")[0])


def judge(row):
    if not row.naver_place_name:
        return "no_meta"
    ours, theirs = addr_key(row.address), addr_key(row.naver_road_address)
    if ours and theirs and ours == theirs:
        return "address"
    if gu(row.address) != gu(row.naver_road_address or row.naver_address):
        return "mismatch"
    if row.sim >= NAME_SIM_OK:
        return "name"
    if (ours and theirs and ours[:2] == theirs[:2] and abs(bldg_no(ours) - bldg_no(theirs)) <= NEAR_NUM_GAP
            and row.sim >= NAME_SIM_NEAR):
        return "near"
    return "mismatch"


def main(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    df = pd.read_sql(
        """SELECT store_id, area_name, store_name, address, naver_place_id AS place_id, naver_place_name,
                  naver_road_address, naver_address, naver_category, naver_review_total, review_status
           FROM excel_dining_stores
           WHERE search_status='MATCHED' AND naver_place_id IS NOT NULL""", con)
    df = df.fillna({"naver_place_name": "", "naver_road_address": ""})
    df["sim"] = [round(name_sim(a, b), 3) for a, b in zip(df.store_name, df.naver_place_name)]
    df["match_status"] = df.apply(judge, axis=1)

    # 같은 플레이스에 여러 가게: 판정 등급 → 이름 유사도 → store_id 순으로 1등만 남긴다
    df["_rank"] = df.match_status.map(RANK)
    df = df.sort_values(["place_id", "_rank", "sim", "store_id"], ascending=[True, False, False, True])
    df["n_shared"] = df.groupby("place_id").store_id.transform("size")
    loser = df.duplicated("place_id") & (df.match_status != "mismatch")
    df.loc[loser, "match_status"] = "shared_loser"
    df["keep"] = ~df.match_status.isin(["mismatch", "shared_loser"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.drop(columns="_rank").sort_values("store_id").to_csv(OUT, index=False, encoding="utf-8-sig")
    print(df.match_status.value_counts().to_string())
    print(f"공유 플레이스 {df[df.n_shared > 1].place_id.nunique()}곳, 유지 {int(df.keep.sum())} / {len(df)} → {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DB)
