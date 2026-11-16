#!/usr/bin/env python3
"""서울 생활이동 행정동 OD(한 달) → 서울 전 출발지의 '도착=기타 장소(E)' 이동 패널(동 단위).

열: origin, dest(통계 7자리, 서울 11만), otype(출발 체류지 H 집/W 직장·학교/E 기타),
    slot(점심 11~13·오후 14~16·저녁 17~20·심야 21~23·기타), age20(20·25세 구간이면 1), cnt, masked
'*'(3명 이하)는 채우지 않는다(쓰는 쪽에서 2명).

실행: ~/.venvs/maximus/bin/python 분석/build_seoul_od_panel.py 202606
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "데이터/원천/seoul_living_migration"
OUT = HERE / "데이터/가공/od_eval"
COLS = ["도착시간", "출발 행정동 코드", "도착 행정동 코드", "나이", "이동유형", "이동인구(합)"]
SLOT_OF_HOUR = {**{h: "점심" for h in (11, 12, 13)}, **{h: "오후" for h in (14, 15, 16)},
                **{h: "저녁" for h in (17, 18, 19, 20)}, **{h: "심야" for h in (21, 22, 23)}}
KEYS = ["origin", "dest", "otype", "slot", "age20"]


def main() -> None:
    month = sys.argv[1] if len(sys.argv) > 1 else "202606"
    z = zipfile.ZipFile(SRC / f"living_migration_admdong_{month}.zip")
    parts = []
    for info in z.infolist():
        for ch in pd.read_csv(z.open(info), encoding="cp949", dtype=str, usecols=COLS, chunksize=3_000_000):
            ch = ch[ch["이동유형"].str.endswith("E") & ch["출발 행정동 코드"].str.startswith("11")
                    & ch["도착 행정동 코드"].str.startswith("11")]
            df = pd.DataFrame({
                "origin": ch["출발 행정동 코드"], "dest": ch["도착 행정동 코드"], "otype": ch["이동유형"].str[0],
                "slot": ch["도착시간"].astype(int).map(SLOT_OF_HOUR).fillna("기타"),
                "age20": ch["나이"].isin(["20", "25"]).astype(np.int8),
                "cnt": pd.to_numeric(ch["이동인구(합)"], errors="coerce").fillna(0.0),
                "masked": ch["이동인구(합)"].eq("*").astype(np.int32)})
            parts.append(df.groupby(KEYS, as_index=False)[["cnt", "masked"]].sum())
    out = pd.concat(parts).groupby(KEYS, as_index=False)[["cnt", "masked"]].sum()
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / f"seoul_od_E_{month}.csv.gz", index=False)
    print(month, len(out), f"합 {out.cnt.sum() + 2 * out.masked.sum():,.0f}")


if __name__ == "__main__":
    main()
