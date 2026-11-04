"""행정안전부_식품 인허가 조회서비스(일반음식점 15154916, 휴게음식점 rest_cafes, 제과점 bakeries)에서 지자체 코드별 전체 인허가를 받는다(폐업 포함).

코드 4050000은 용인시 전체(처인·기흥·수지), 5540000 광주시, 3780000 성남시 전체.
페이지(100건) 응답을 캐시해 끊겨도 이어받는다. 키는 출력하지 않는다.
실행: zsh -ic '~/.venvs/maximus/bin/python -I 분석/모현/download_restaurant_licenses.py <저장 csv> [<서비스>] <코드> [<코드> ...]'
      서비스 생략 = general_restaurants. --active 를 붙이면 영업 중(SALS_STTS_CD=01)만 받는다(서울처럼 큰 지역용)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://apis.data.go.kr/1741000/{service}/info"
CACHE = (Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())) / "데이터/캐시/모현_인허가"


def page(service: str, code: str, n: int, active: bool = False) -> dict:
    p = CACHE / ("active_" * active + (f"{code}_{n}.json" if service == "general_restaurants" else f"{service}_{code}_{n}.json"))
    if not p.exists():
        q = urllib.parse.urlencode({"serviceKey": os.environ["DATA_GO_KR_KEY"], "pageNo": n, "numOfRows": 100,
                                    "returnType": "json", "cond[OPN_ATMY_GRP_CD::EQ]": code,
                                    **({"cond[SALS_STTS_CD::EQ]": "01"} if active else {})})
        for i in range(6):
            try:
                with urllib.request.urlopen(f"{URL.format(service=service)}?{q}", timeout=60) as r:
                    raw = r.read()
                json.loads(raw)["response"]["body"]
                p.write_bytes(raw)
                break
            except Exception as e:
                print("retry", code, n, i, type(e).__name__)
                time.sleep(5 * (i + 1))
        else:
            raise RuntimeError(f"{code} page {n}")
    return json.loads(p.read_text())["response"]["body"]


def main() -> None:
    active = "--active" in sys.argv
    out, rest = Path(sys.argv[1]), [a for a in sys.argv[2:] if a != "--active"]
    service = "general_restaurants" if rest[0].isdigit() else rest.pop(0)
    codes = rest
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for code in codes:
        n, got = 1, 0
        while True:
            b = page(service, code, n, active)
            items = b["items"]["item"] if b.get("items") else []
            rows += items
            got += len(items)
            if got >= int(b["totalCount"]) or not items:
                break
            n += 1
        print(code, got, b["totalCount"])
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
