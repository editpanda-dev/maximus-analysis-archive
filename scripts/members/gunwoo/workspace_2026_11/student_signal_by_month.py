#!/usr/bin/env python3
"""학생 신호 점검: 학기 중(3~6월) vs 방학(12~2월, 7월)에 캠퍼스 동의 '학교(W)→기타(E)' 20대 이동이 줄어드나.

학생 근사가 맞다면 방학에 캠퍼스 동 20대 W→E가 다른 동보다 크게 줄어야 한다.
실행: ~/.venvs/maximus/bin/python 분석/student_signal_by_month.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_dongdaemun_od_inflow import stat_to_admin  # noqa: E402
from eval_generalization import MASK_FILL, PANEL  # noqa: E402
from student_flows import campus_dongs  # noqa: E402

SEMESTER = {"202603", "202604", "202605", "202606"}


def main() -> None:
    xw, _ = stat_to_admin()
    camp = campus_dongs(xw)
    ddm = set(camp.loc[camp.district == "동대문구", "stat_code"])
    rows = []
    for f in sorted(PANEL.glob("seoul_od_E_*.csv.gz")):
        m = f.name.split("_")[-1][:6]
        p = pd.read_csv(f, dtype={"origin": str, "dest": str})
        p = p[(p.otype == "W") & (p.origin != p.dest)]
        p["v"] = p.cnt + MASK_FILL * p.masked
        g = p.groupby(["origin", "age20"]).v.sum().unstack(fill_value=0)
        grp = pd.Series("그 밖", index=g.index)
        grp[g.index.isin(camp.stat_code)] = "캠퍼스 동"
        grp[g.index.isin(ddm)] = "동대문 캠퍼스"
        s = g.groupby(grp).sum()
        for k, r in s.iterrows():
            rows.append({"month": m, "group": k, "w20": r[1], "w_all": r.sum(), "share20": r[1] / r.sum()})
    d = pd.DataFrame(rows)
    d["학기"] = d.month.isin(SEMESTER).map({True: "학기 중", False: "방학"})
    piv = d.pivot(index="month", columns="group", values="w20")
    idx = piv / piv.loc[sorted(SEMESTER)].mean()  # 학기 평균 = 1
    print("20대 W→E 이동량 (학기 평균 대비)\n", idx.round(2).to_string())
    print("\n20대 비중\n", d.pivot(index="month", columns="group", values="share20").round(3).to_string())
    d.to_csv(PANEL / "students" / "student_signal_by_month.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
