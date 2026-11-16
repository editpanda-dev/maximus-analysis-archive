# -*- coding: utf-8 -*-
"""서울시 음식점 인허가 데이터 내려받기 (일반음식점·휴게음식점).

면적(FACILTOTSCP 시설총규모 ㎡), 영업상태, 위생업태, 좌표(EPSG:5174)를 점포에 붙이는 데 쓴다.
키는 SEOUL_OPENAPI_KEY 환경변수에서 읽고 출력하지 않는다. 결과는 로컬 원천 폴더에만 둔다.

실행: ~/.venvs/maximus/bin/python 분석/download_localdata.py
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

KEY = os.environ.get("SEOUL_OPENAPI_KEY", "").strip()
if not KEY:
    sys.exit("SEOUL_OPENAPI_KEY is not set")
OUT = Path(__file__).resolve().parents[1] / "데이터/원천/seoul_openapi"
SERVICES = {"LOCALDATA_072404": "localdata_general_restaurant",
            "LOCALDATA_072405": "localdata_rest_restaurant"}
KEEP = ["MGTNO", "BPLCNM", "TRDSTATENM", "DTLSTATENM", "APVPERMYMD", "DCBYMD", "UPTAENM",
        "SITEWHLADDR", "RDNWHLADDR", "X", "Y", "SITEAREA", "FACILTOTSCP", "MULTUSNUPSOYN"]


def fetch(svc, start, end):
    url = f"http://openapi.seoul.go.kr:8088/{KEY}/json/{svc}/{start}/{end}/"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                body = json.loads(r.read().decode("utf-8")).get(svc)
            if body is None:
                raise RuntimeError("no body")
            return body["row"]
        except Exception as e:  # 일시 오류 재시도, URL은 찍지 않는다
            if attempt == 4:
                raise RuntimeError(f"{svc} {start}-{end}: {type(e).__name__}: {str(e)[:150]}")
            time.sleep(3 * (attempt + 1))


for svc, name in SERVICES.items():
    with urllib.request.urlopen(f"http://openapi.seoul.go.kr:8088/{KEY}/json/{svc}/1/1/", timeout=60) as r:
        total = int(json.loads(r.read().decode("utf-8"))[svc]["list_total_count"])
    ranges = [(s, min(s + 999, total)) for s in range(1, total + 1, 1000)]
    with ThreadPoolExecutor(4) as ex:
        pages = list(ex.map(lambda se: fetch(svc, *se), ranges))
    df = pd.DataFrame([row for p in pages for row in p])[KEEP]
    df = df.apply(lambda c: c.astype(str).str.strip())
    path = OUT / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"{svc}: {len(df):,} / {total:,} rows, 영업 {int((df.TRDSTATENM == '영업/정상').sum()):,} -> {path.name}")
