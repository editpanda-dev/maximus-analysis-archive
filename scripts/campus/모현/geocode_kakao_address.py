"""주소 열을 카카오 주소검색으로 좌표화한다. 주소 검색이 비면 '상호 + 시군구' 키워드 검색으로 한 번 더 찾는다.

괄호·쉼표 뒤(층·호·건물명)는 떼고 부른다. 응답은 데이터/캐시/모현_kakao_geocode/에 캐시. 카카오 응답이라 재배포 금지.
실행: zsh -ic '~/.venvs/maximus/bin/python -I 분석/모현/geocode_kakao_address.py <입력 csv|tsv> <id 열> <주소 열> <저장 csv> [<상호 열>]'
출력 열: <id 열>, kakao_lat, kakao_lon, geocode_by(address|keyword)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

CACHE = (Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())) / "데이터/캐시/모현_kakao_geocode"


def kakao(kind: str, query: str) -> list[dict]:
    p = CACHE / f"{kind}_{hashlib.md5(query.encode()).hexdigest()}.json"
    if not p.exists():
        q = urllib.parse.urlencode({"query": query, "size": 1})
        req = urllib.request.Request(f"https://dapi.kakao.com/v2/local/search/{kind}.json?{q}",
                                     headers={"Authorization": f"KakaoAK {os.environ['KAKAO_REST_API_KEY']}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            p.write_bytes(r.read())
        time.sleep(0.05)
    return json.loads(p.read_text()).get("documents", [])


def clean(addr: str) -> str:
    return re.sub(r"\s+", " ", re.split(r"[,(]", str(addr))[0]).strip()


def main() -> None:
    src, id_col, addr_col, out = sys.argv[1:5]
    name_col = sys.argv[5] if len(sys.argv) > 5 else None
    CACHE.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(src, dtype=str, sep="\t" if src.endswith(".tsv") else ",")
    rows = []
    for r in df.itertuples(index=False):
        addr = clean(getattr(r, addr_col))
        docs, by = kakao("address", addr), "address"
        if not docs and name_col:
            docs, by = kakao("keyword", f"{' '.join(addr.split()[:2])} {getattr(r, name_col)}"), "keyword"
        lat, lon = (float(docs[0]["y"]), float(docs[0]["x"])) if docs else (None, None)
        rows.append({id_col: getattr(r, id_col), "kakao_lat": lat, "kakao_lon": lon, "geocode_by": by if docs else None})
    res = pd.DataFrame(rows)
    res.to_csv(out, index=False, encoding="utf-8-sig")
    print(src, len(res), "ok", int(res.kakao_lat.notna().sum()), res.geocode_by.value_counts().to_dict())


if __name__ == "__main__":
    main()
