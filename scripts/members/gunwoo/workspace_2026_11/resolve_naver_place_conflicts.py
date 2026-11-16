"""한 place_id에 여러 store_id가 붙은 충돌을 네이버 지도 검색 주소로 자동 판정.

입력: 데이터/가공/naver_reviews/place_store_conflicts.csv (clean_naver_dining_reviews.py 출력)
출력: 데이터/가공/naver_reviews/place_store_resolution.csv
캐시: 데이터/캐시/naver_search/conflicts/<검색어>.json

판정 순서 (place별):
  1) 후보 가게 이름으로 네이버 지도를 검색해 결과 중 id == place_id 인 항목의 도로명주소·이름을 얻는다.
  2) 그 주소(구+도로명+건물번호)와 같은 주소의 후보가 1곳 → address.
     같은 주소 후보가 여럿(소상공인 데이터 중복 등록) → 네이버 이름과 가장 닮은 곳, 동점이면 store_id 순 첫째 → address_dup.
  3) 주소 일치 후보가 없으면 네이버 이름 유사도 0.8 이상 단독 1위 → name.
  4) 그 외 → unresolved (모든 후보 리뷰 유지).
실행 후 clean_naver_dining_reviews.py 를 다시 돌리면 판정 결과가 정제본에 반영된다.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "데이터/가공/naver_reviews"
CACHE = ROOT / "데이터/캐시/naver_search/conflicts"
SEOUL_CENTER = "37.5665,126.9780"
NAME_SIM_MIN = 0.8


def norm_name(s):
    s = re.sub(r"\(.*?\)", "", str(s or "")).lower()
    return re.sub(r"[^가-힣a-z0-9]", "", s)


def addr_key(s):
    """'서울특별시 종로구 종로40가길 5 1층' -> ('종로구', '종로40가길', '5')"""
    m = re.search(r"(\S+구)\s+(\S+(?:로|길))\s*(\d+(?:-\d+)?)", str(s or ""))
    return m.groups() if m else None


def search(query):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (re.sub(r"[^\w가-힣]", "_", query) + ".json")
    if path.exists():
        return json.loads(path.read_text())
    url = "https://map.naver.com/p/api/search/instant-search?" + urllib.parse.urlencode(
        {"query": query, "coords": SEOUL_CENTER})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://map.naver.com/"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:  # 검색어에 따라 400이 난다. 캐시하지 않고 건너뜀
        print(f"  검색 실패 {e.code}: {query}")
        time.sleep(0.5)
        return {}
    path.write_text(json.dumps(data, ensure_ascii=False))
    time.sleep(2)  # 0.5초 간격에서 약 100건 후 400 차단됨
    return data


def lookup_place(place_id, queries):
    for q in queries:
        for p in search(q).get("place", []):
            if p.get("id") == place_id:
                return p.get("title"), p.get("roadAddress")
    return None, None


def decide(place_id, cand):
    names = list(dict.fromkeys(cand.store_name))
    gu = [k[0] for k in cand.address.map(addr_key) if k]
    queries = names + [f"{n} {g}" for n in names for g in dict.fromkeys(gu)]
    title, road = lookup_place(place_id, queries)
    title = title or cand.naver_place_name.max() or ""
    sims = cand.store_name.map(lambda s: SequenceMatcher(None, norm_name(s), norm_name(title)).ratio() if title else 0.0)
    cand = cand.assign(sim=sims.values)

    key = addr_key(road)
    if key:
        same = cand[cand.address.map(addr_key) == key]
        if len(same) == 1:
            return same.store_id.iloc[0], "address", title, road
        if len(same) > 1:
            best = same.sort_values(["sim", "store_id"], ascending=[False, True]).iloc[0]
            return best.store_id, "address_dup", title, road
    top = cand.sort_values("sim", ascending=False)
    if top.sim.iloc[0] >= NAME_SIM_MIN and (len(top) == 1 or top.sim.iloc[0] > top.sim.iloc[1]):
        return top.store_id.iloc[0], "name", title, road
    return None, "unresolved", title, road


def main():
    conf = pd.read_csv(OUT_DIR / "place_store_conflicts.csv", dtype=str, keep_default_na=False)
    rows = []
    for pid, cand in conf.groupby("place_id"):
        winner, method, title, road = decide(pid, cand)
        for r in cand.itertuples():
            rows.append({"place_id": pid, "store_id": r.store_id, "store_name": r.store_name,
                         "address": r.address, "naver_title": title, "naver_road_address": road,
                         "method": method, "keep": winner is None or r.store_id == winner})
    res = pd.DataFrame(rows)
    res.to_csv(OUT_DIR / "place_store_resolution.csv", index=False, encoding="utf-8-sig")
    print(res.drop_duplicates("place_id").method.value_counts().to_dict())
    print(f"제외 대상 store {int((~res.keep).sum())}개 → {OUT_DIR / 'place_store_resolution.csv'}")


if __name__ == "__main__":
    main()
