"""공공데이터포털 표준데이터를 포털 '다운로드' 버튼과 같은 경로(/download/*.json)로 받는다. 키 불필요.

경기도 용인시·광주시 행만 남긴다(전국 파일은 크다).
전국체육시설표준데이터(15096288)는 파일 내려받기가 없어(REST 전용, 포털 행 수 0) 빠진다 → API 활용신청 필요.
실행: ~/.venvs/maximus/bin/python -I 분석/모현/download_standard_data.py <저장폴더>
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://www.data.go.kr"
DATASETS = {
    "15012890": "city_parks",          # 전국도시공원정보표준데이터
    "15013117": "public_facility_open",  # 전국공공시설개방정보표준데이터
}
KEEP = ("용인", "광주시")


def get_json(path: str, params: list[tuple[str, str]]) -> dict:
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.loads(r.read())
        except Exception as e:  # 포털이 가끔 끊긴다
            print("retry", i, type(e).__name__)
            time.sleep(5 * (i + 1))
    raise RuntimeError(path)


def download(pk: str) -> pd.DataFrame:
    head = get_json("/download/columList.json", [("pk", pk), ("ext", "CSV")])
    cols = head["columList"]
    tv = head["tableVO"]
    rows, per = [], 10000
    pages = -(-int(head["totalCount"]) // per)
    for page in range(1, pages + 1):
        params = [("publicDataPk", pk), ("svcTableNm", tv["svcTableNm"]), ("perPage", per), ("page", page),
                  ("totalCount", head["totalCount"])] + [("colNmList", c) for c in tv["colNmList"]]
        rows += get_json("/download/standard.json", params)
        print(pk, page, "/", pages, len(rows))
    df = pd.DataFrame(rows)
    return df[[c["columCode"] for c in cols if c["columCode"] in df]].rename(
        columns={c["columCode"]: c["columNm"] for c in cols})


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for pk, name in DATASETS.items():
        df = download(pk)
        text = df.astype(str).agg(" ".join, axis=1)
        local = df[text.str.contains("경기") & text.str.contains("|".join(KEEP))]
        local.to_csv(out / f"{name}_yongin_gwangju_{pk}.csv", index=False, encoding="utf-8-sig")
        print(name, "전국", len(df), "→ 용인·광주", len(local))


if __name__ == "__main__":
    main()
