#!/usr/bin/env python3
"""왕십리 쏠림 원인 점검: '대학 동 → 대학가·청년 상권' 친화도.

도착동마다 출발동별 비중을 거리감쇠(2차 log 거리 회귀)로 기대치와 비교해 배율(실제/기대)을 낸다.
그 배율을 출발동이 캠퍼스 동인지, 20대만 볼 때인지, 도착동이 캠퍼스 인접인지로 나눠 비교한다.
자료: 서울 생활이동 OD 2026-03~06(학기), 도착=기타 장소, 같은 동 안 이동 제외.

실행: ~/.venvs/maximus/bin/python 분석/hub_affinity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_generalization as e  # noqa: E402
from build_serendipity_ranking import haversine_km  # noqa: E402
from student_flows import campus_dongs  # noqa: E402

MONTHS = ["202603", "202604", "202605", "202606"]
DESTS = {"1104056": "행당1동(왕십리역·한양대 옆)", "1105053": "화양동(건대)", "1113065": "신촌동(연대·신촌)",
         "1108060": "안암동(고려대)", "1104065": "성수1가1동(성수)", "1102052": "소공동(명동 옆)", "1123064": "역삼1동(강남역)"}


def ratios(od: pd.DataFrame, oxy: pd.DataFrame, dest: str) -> pd.DataFrame:
    g = pd.DataFrame({"origin": oxy.index}).merge(od[od.dest == dest], on="origin", how="left").fillna({"share": 0})
    g = g[g.origin != dest].copy()
    g["km"] = haversine_km(oxy.loc[g.origin, "lat"].to_numpy(), oxy.loc[g.origin, "lon"].to_numpy(), oxy.at[dest, "lat"], oxy.at[dest, "lon"])
    g = g[g.km < 12]
    x = np.log(g.km.clip(lower=0.3)); X = np.c_[np.ones(len(g)), x, x ** 2]; y = np.log(g.share + 1e-6)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    return g.assign(ratio=np.exp(y - X @ b), dest=dest)


def main() -> None:
    xw, alloc, oxy, *_ = e.load_common()
    camp = set(campus_dongs(xw).stat_code)
    p = pd.concat([pd.read_csv(e.PANEL / f"seoul_od_E_{m}.csv.gz", dtype={"origin": str, "dest": str}) for m in MONTHS])
    p = p[(p.origin != p.dest) & p.origin.isin(oxy.index)]
    p["v"] = p.cnt + 2 * p.masked
    rows = []
    for label, sub in [("전체", p), ("20대", p[p.age20 == 1]), ("20대·학교 출발", p[(p.age20 == 1) & (p.otype == "W")])]:
        od = sub.groupby(["origin", "dest"]).v.sum().reset_index()
        od["share"] = od.v / od.groupby("origin").v.transform("sum")
        for d in DESTS:
            if d not in oxy.index:
                continue
            g = ratios(od, oxy, d)
            g["campus"] = g.origin.isin(camp)
            rows.append({"flow": label, "dest": DESTS[d], "캠퍼스 동 배율": g.loc[g.campus, "ratio"].median(),
                         "다른 동 배율": g.loc[~g.campus, "ratio"].median(), "캠퍼스 동 수": int(g.campus.sum())})
    r = pd.DataFrame(rows)
    r["캠퍼스/다른"] = r["캠퍼스 동 배율"] / r["다른 동 배율"]
    print(r.round(2).to_string(index=False))
    r.to_csv(e.PANEL / "hub_affinity_campus.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
