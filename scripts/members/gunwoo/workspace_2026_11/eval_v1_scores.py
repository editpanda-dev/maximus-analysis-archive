#!/usr/bin/env python3
"""팀 v1 목적 점수(규모 보정판)를 PATH-v0와 같은 생활이동 OD 정답으로 평가한다.

정답·층은 eval_destination_ranking.py와 같다(동대문구 출발동 × 도착 시간대 × 연령, 도착=기타).
목적 ↔ 시간대: 식사=점심·저녁, 카페·쇼핑·공부=오후, 여가문화=심야.
점수만으로 순위를 매기므로 학습이 없고, 8개월 전부를 시험한다.

v1 점수 원본: fork/integrate/team-analysis-2026-11 브랜치 (scratchpad로 꺼낸 CSV 경로를 인자로 받는다)
실행: ~/.venvs/maximus/bin/python 분석/eval_v1_scores.py <v1_csv_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_destination_ranking as ev  # noqa: E402
from build_dongdaemun_od_inflow import stat_to_admin  # noqa: E402

PURPOSE_SLOTS = {"식사": ["점심", "저녁"], "카페": ["오후"], "쇼핑": ["오후"], "공부": ["오후"], "여가문화": ["심야"]}


def load_v1(d: Path) -> dict[str, dict[str, pd.Series]]:
    """목적 → {점수 이름: area_code 인덱스 점수}."""
    fs = pd.read_csv(d / "food_shopping_v1_786_13e42d2.csv", dtype={"area_code": str}).set_index("area_code")
    sn = pd.read_csv(d / "food_shopping_size_neutral_786_d0b6734.csv", dtype={"area_code": str}).set_index("area_code")
    cf = pd.read_csv(d / "cafe_size_adjusted_786_6c591a7.csv", dtype={"area_code": str}).set_index("area_code")
    le = pd.read_csv(d / "official_area_leisure_culture_v1_786.csv", dtype={"area_code": str}).set_index("area_code")
    cafe_adj = cf["cafe_size_adjusted_full_score"].fillna(cf["cafe_size_adjusted_supply_only_score"])
    return {
        "식사": {"식사·쇼핑 v1 (김건우)": fs["food_score"], "식사 규모중립 v1": sn["food_meal_score_v1"]},
        "쇼핑": {"식사·쇼핑 v1 (김건우)": fs["shopping_score"], "쇼핑 규모중립 v1": sn["shopping_destination_score_v1"]},
        "카페": {"카페 규모보정 (장한별)": cafe_adj, "카페 원점수 (장한별)": cf["full_score"].fillna(cf["supply_only_score"])},
        # study_v1_score는 786곳 전부 비어 있다(status=incomplete_stay_evidence). 현행 체류 점수로 대신한다.
        "공부": {"공부 체류 현행 (장한별)": cf["study_stay_current_score"]},
        "여가문화": {"여가 규모보정 v1 (지우진)": le["leisure_size_adjusted_score"], "여가 야간 2025 (지우진)": le["nightlife_2025_score"]},
    }


def main(v1_dir: Path) -> None:
    months = sorted(p.stem.split("_")[-1] for p in ev.PANEL.glob("ddm_od_E_*.csv"))
    xw, ov = stat_to_admin()
    alloc = ev.dong_to_area(xw, ov)
    area, purpose = ev.serp.load_inputs(ev.REPO, 20254, use_movement=True)
    codes = area["area_code"].astype(str).to_numpy()
    path = purpose.pivot(index="area_code", columns="purpose", values="path_v0_score")
    path.index = path.index.astype(str)
    path = path.reindex(codes)

    lab = pd.concat([ev.month_labels(m, alloc) for m in months])
    lab["area_code"] = lab["area_code"].astype(str)
    lab = lab[lab["area_code"].isin(codes) & lab["origin"].str.startswith("11060")]
    key = ["origin", "slot", "age_grp", "area_code"]
    wide = lab.pivot_table(index=key, columns="month", values="y", aggfunc="sum").reset_index()
    strata = wide[["origin", "slot", "age_grp"]].drop_duplicates()
    full = strata.merge(pd.DataFrame({"area_code": codes}), how="cross")
    # 출발동에 걸친 상권은 그 출발지 후보에서 뺀다(같은 동 안 이동을 정답에서 뺐으므로, eval_generalization.py와 같은 규칙)
    own = alloc[alloc["w"] > 0][["stat_code", "area_code"]].rename(columns={"stat_code": "origin"}).assign(_own=1)
    own["area_code"] = own["area_code"].astype(str)
    full = full.merge(own, on=["origin", "area_code"], how="left")
    full = full[full["_own"].isna()].drop(columns="_own")
    full = full.merge(wide, on=key, how="left").fillna({m: 0.0 for m in months})

    # 거리순 기준선: 출발동 중심(겹친 상권 중심의 면적 가중 평균)에서 가까운 순
    a2 = area.assign(area_code=area["area_code"].astype(str))
    o = ov.assign(area_code=ov["area_code"].astype(str)).merge(a2[["area_code", "lat", "lon"]], on="area_code")
    oc = xw[xw["stat_code"].str.startswith("11060")].merge(o, on="admin_code")
    oc["ww"] = oc["weight"] * oc["overlap_m2"]
    oxy = oc.groupby("stat_code").apply(lambda g: pd.Series({"lat": np.average(g.lat, weights=g.ww), "lon": np.average(g.lon, weights=g.ww)}))
    axy = a2.set_index("area_code").loc[codes, ["lat", "lon"]]

    v1 = load_v1(v1_dir)
    rows = []
    for pur, slots in PURPOSE_SLOTS.items():
        cand = {"PATH-v0 (1주차 기준선)": path[pur], **v1[pur]}
        cov = {}
        for name, s in cand.items():
            s = s.reindex(codes)
            cov[name] = s.notna().mean()
            cand[name] = s.fillna(s.min() - 1).to_numpy()  # 점수 없는 상권은 맨 뒤
        cov["거리순"] = 1.0
        sub = full[full["slot"].isin(slots)]
        for (o_, s_, a_), idx in sub.groupby(["origin", "slot", "age_grp"]).indices.items():
            g = sub.iloc[idx]
            pos = pd.Index(codes).get_indexer(g["area_code"])
            if o_ not in oxy.index:
                continue
            dist = -ev.serp.haversine_km(np.full(len(codes), oxy.at[o_, "lat"]), np.full(len(codes), oxy.at[o_, "lon"]),
                                         axy["lat"].to_numpy(), axy["lon"].to_numpy())
            scores = {**cand, "거리순": dist}
            for T in months:
                y = g[T].to_numpy()
                if y.sum() <= 0:
                    continue
                for name, sc in scores.items():
                    n, r = ev.ndcg_recall(y, sc[pos])
                    rows.append({"purpose": pur, "model": name, "coverage": cov[name], "month": T,
                                 "origin": o_, "slot": s_, "age_grp": a_, "ndcg10": n, "recall10": r})

    res = pd.DataFrame(rows)
    out = ev.PANEL / "v1_scores"
    out.mkdir(exist_ok=True)
    res.to_csv(out / "eval_v1_by_stratum.csv", index=False, encoding="utf-8-sig")
    summ = (res.groupby(["purpose", "model", "age_grp"])
               .agg(ndcg10=("ndcg10", "mean"), recall10=("recall10", "mean"), coverage=("coverage", "first"), n=("ndcg10", "size"))
               .round(3).reset_index())
    summ.to_csv(out / "eval_v1_summary.csv", index=False, encoding="utf-8-sig")
    print(summ.to_string(index=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
