#!/usr/bin/env python3
"""학생 신호 점검 2: 요일별. 캠퍼스 동의 20대 '학교(W)→기타(E)' 이동이 주말에 더 크게 주나.

원천: 서울 생활이동 행정동 OD 월별 zip(요일 열: 월~일, 그 달의 해당 요일 합계).
하루 평균 = 요일 합 / 그 달 그 요일 날짜 수(공휴일은 따로 빼지 않음).
학생 근사가 맞다면 캠퍼스 동은 주말(토·일)에 평일보다 훨씬 크게 줄고, 다른 동은 덜 준다.

실행: ~/.venvs/maximus/bin/python 분석/student_signal_by_weekday.py
"""

from __future__ import annotations

import calendar
import sys
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dongdaemun_od_inflow import stat_to_admin  # noqa: E402
from student_flows import campus_dongs  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "데이터/원천/seoul_living_migration"
OUT = HERE / "데이터/가공/od_eval/students"
DAYS = ["월", "화", "수", "목", "금", "토", "일"]
SEMESTER = {"202603", "202604", "202605", "202606"}


def month_weekday(month: str, campus: set[str], ddm: set[str]) -> pd.DataFrame:
    z = zipfile.ZipFile(SRC / f"living_migration_admdong_{month}.zip")
    parts = []
    cols = ["요일", "출발 행정동 코드", "도착 행정동 코드", "나이", "이동유형", "이동인구(합)"]
    for info in z.infolist():
        for ch in pd.read_csv(z.open(info), encoding="cp949", dtype=str, usecols=cols, chunksize=3_000_000):
            ch = ch[(ch["이동유형"] == "WE") & ch["출발 행정동 코드"].str.startswith("11")
                    & (ch["출발 행정동 코드"] != ch["도착 행정동 코드"])]
            o = ch["출발 행정동 코드"]
            grp = pd.Series("그 밖", index=ch.index).mask(o.isin(campus), "캠퍼스 동").mask(o.isin(ddm), "동대문 캠퍼스")
            v = pd.to_numeric(ch["이동인구(합)"], errors="coerce").fillna(2.0)
            parts.append(pd.DataFrame({"group": grp, "day": ch["요일"], "age20": ch["나이"].isin(["20", "25"]), "v": v})
                         .groupby(["group", "day", "age20"], as_index=False)["v"].sum())
    d = pd.concat(parts).groupby(["group", "day", "age20"], as_index=False)["v"].sum()
    y, m = int(month[:4]), int(month[4:])
    ndays = {DAYS[i]: sum(1 for w in calendar.Calendar().itermonthdays2(y, m) if w[0] and w[1] == i) for i in range(7)}
    d["per_day"] = d["v"] / d["day"].map(ndays)
    return d.assign(month=month)


def main() -> None:
    xw, _ = stat_to_admin()
    camp = campus_dongs(xw)
    campus, ddm = set(camp.stat_code), set(camp.loc[camp.district == "동대문구", "stat_code"])
    months = sorted(p.stem.split("_")[-1] for p in SRC.glob("living_migration_admdong_*.zip"))
    d = pd.concat([month_weekday(m, campus, ddm) for m in months])
    d.to_csv(OUT / "student_signal_by_weekday.csv", index=False, encoding="utf-8-sig")
    d["period"] = d["month"].isin(SEMESTER).map({True: "학기", False: "방학"})
    d["daytype"] = d["day"].map(lambda x: x if x in ("토", "일") else "평일")
    # 하루 평균(평일은 5개 요일 평균)
    g = d.groupby(["period", "daytype", "group", "age20", "month"])["per_day"].sum().reset_index()
    g.loc[g.daytype == "평일", "per_day"] /= 5
    g = g.groupby(["period", "daytype", "group", "age20"])["per_day"].mean().unstack("age20")
    g.columns = ["20대 외", "20대"]
    g["20대 비중"] = g["20대"] / (g["20대"] + g["20대 외"])
    base = g.loc[("학기", "평일"), "20대"]
    g["20대(학기 평일=1)"] = g["20대"] / g.index.get_level_values("group").map(base).to_numpy()
    print(g[["20대(학기 평일=1)", "20대 비중"]].round(3).unstack("group").to_string())
    # 요일별(학기)
    s = d[(d.period == "학기") & d.age20].groupby(["group", "day"])["per_day"].mean().unstack("day")[DAYS]
    print("\n학기 20대 W→E 하루 평균, 월요일=1\n", s.div(s["월"], axis=0).round(2).to_string())


if __name__ == "__main__":
    main()
