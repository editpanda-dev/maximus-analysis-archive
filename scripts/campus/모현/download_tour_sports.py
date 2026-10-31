"""TourAPI(캠퍼스 반경 20km 전 유형)와 국민체육진흥공단 전국체육시설(용인·광주, 영업 중)을 받는다.

data.go.kr 키(DATA_GO_KR_KEY) 필요. 키는 출력하지 않는다.
실행: zsh -ic '~/.venvs/maximus/bin/python -I 분석/모현/download_tour_sports.py <저장폴더>'
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

KEY = os.environ["DATA_GO_KR_KEY"]
CAMPUS = (37.33707, 127.26543)


def get(url: str, params: dict) -> dict:
    q = urllib.parse.urlencode({"serviceKey": KEY, **params})
    for i in range(5):
        try:
            with urllib.request.urlopen(f"{url}?{q}", timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            print("retry", i, type(e).__name__)
            time.sleep(5 * (i + 1))
    raise RuntimeError(url)


def items(body: dict) -> list[dict]:
    it = body.get("items") or {}
    it = it.get("item", []) if isinstance(it, dict) else []
    return it if isinstance(it, list) else [it]


def tour() -> pd.DataFrame:
    rows, page = [], 1
    while True:
        b = get("https://apis.data.go.kr/B551011/KorService2/locationBasedList2",
                {"pageNo": page, "numOfRows": 1000, "MobileOS": "ETC", "MobileApp": "maximus", "_type": "json",
                 "mapX": CAMPUS[1], "mapY": CAMPUS[0], "radius": 20000})["response"]["body"]
        got = items(b)
        rows += got
        if not got or len(rows) >= int(b["totalCount"]):
            return pd.DataFrame(rows)
        page += 1


def sports() -> pd.DataFrame:
    rows = []
    for city in ("용인시", "광주시"):
        page = 1
        while True:
            b = get("https://apis.data.go.kr/B551014/SRVC_API_SFMS_FACI/TODZ_API_SFMS_FACI",
                    {"pageNo": page, "numOfRows": 1000, "resultType": "json", "cp_nm": "경기도", "cpb_nm": city})["response"]["body"]
            got = items(b)
            rows += got
            if not got or page * 1000 >= int(b["totalCount"]):
                break
            page += 1
        print(city, b["totalCount"])
    return pd.DataFrame(rows)


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    t = tour()
    t.to_csv(out / "tourapi_location_20km_20261030.csv", index=False, encoding="utf-8-sig")
    print("tour", len(t), t.contenttypeid.value_counts().to_dict())
    s = sports()
    s.to_csv(out / "sports_facilities_yongin_gwangju_20261030.csv", index=False, encoding="utf-8-sig")
    print("sports", len(s), s.cpb_nm.value_counts().to_dict(), s.faci_stat_nm.value_counts().head(4).to_dict())


if __name__ == "__main__":
    main()
