#!/usr/bin/env python3
"""서울 생활이동 행정동 OD(월별 zip) → 동대문구 출발 비일상 이동 패널(동 단위).

남기는 것: 출발이 동대문구(11060xx), 도착 유형 E(기타 장소)인 이동.
열: month, origin(통계 7자리), dest(통계 7자리), hour(도착시간), age(5세 단위), cnt, masked('*' 칸 수)
'*'(3명 이하)는 여기서 채우지 않는다. 쓰는 쪽에서 2명으로 채운다.

실행: ~/.venvs/maximus/bin/python 분석/build_ddm_od_panel.py 202603 202604 ...  (인자 없으면 받은 달 전부)
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "데이터/원천/seoul_living_migration"
OUT = HERE / "데이터/가공/od_eval"
COLS = ["도착시간", "출발 행정동 코드", "도착 행정동 코드", "나이", "이동유형", "이동인구(합)"]


def build_month(month: str) -> pd.DataFrame:
    z = zipfile.ZipFile(SRC / f"living_migration_admdong_{month}.zip")
    parts = []
    for info in z.infolist():
        for ch in pd.read_csv(z.open(info), encoding="cp949", dtype=str, usecols=COLS, chunksize=2_000_000):
            ch = ch[ch["출발 행정동 코드"].str.startswith("11060") & ch["이동유형"].str.endswith("E")]
            ch = ch.assign(cnt=pd.to_numeric(ch["이동인구(합)"], errors="coerce").fillna(0.0),
                           masked=ch["이동인구(합)"].eq("*").astype(int))
            parts.append(ch.groupby(["출발 행정동 코드", "도착 행정동 코드", "도착시간", "나이"], as_index=False)[["cnt", "masked"]].sum())
    df = pd.concat(parts).groupby(["출발 행정동 코드", "도착 행정동 코드", "도착시간", "나이"], as_index=False)[["cnt", "masked"]].sum()
    df.columns = ["origin", "dest", "hour", "age", "cnt", "masked"]
    df.insert(0, "month", month)
    return df


def main() -> None:
    months = sys.argv[1:] or sorted(p.stem.split("_")[-1] for p in SRC.glob("living_migration_admdong_*.zip"))
    OUT.mkdir(parents=True, exist_ok=True)
    for m in months:
        f = OUT / f"ddm_od_E_{m}.csv"
        if f.exists():
            continue
        df = build_month(m)
        df.to_csv(f, index=False)
        print(m, len(df), f"합 {df.cnt.sum() + 2 * df.masked.sum():,.0f}")


if __name__ == "__main__":
    main()
