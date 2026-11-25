# -*- coding: utf-8 -*-
"""숨은 상권 결합안 v1 (2026-11-25): 숨은 상권 ABC(11-22) 뼈대 + SERP-v1.2의 실제 이동 신호.

ABC는 업종 구성·매출만 써서 "동대문구민이 이미 가는 곳"을 가려내지 못했다(ABC 문서 7절 한계 2).
SERP-v1.2는 생활이동 OD로 그걸 재지만 목록이 성수·건대로 몰렸다. 둘을 이렇게 잇는다.

  1) 방문 가능성(C)  30분 대중교통 도달률(오전 8시·오후 2시·오후 7시 평균) ≥ 0.5               ← ABC
  2) 늘 가던 곳 제외  회기역 가까운 20 ∪ 매출 상위 20                                        ← ABC
                     ∪ 실제 유입 상위 20 · 동료보다 3배 넘게 가는 거점(SERP inertia)          ← SERP (추가)
  3) 덜 가는 곳만     8달 중 7달 이상 동대문구민이 비슷한 조건 동료보다 덜 간 상권(under_months ≥ 7) ← SERP (추가)
  4) 관련성(A1)       (목적 점포 + k·서울 평균 비율) ÷ (전체 점포 + k), k는 베타-이항 적률추정     ← ABC
  5) 새로움           상위 10곳 중 4곳 이상 매출 하위 50% 상권                                  ← ABC
  6) 다양성           MMR: 0.7·A1 백분위 − 0.3·max(0.5·업종 구성 코사인 + 0.5·exp(−거리km/1.5)) ← ABC

연령: SERP의 U·관성은 연령마다 다르다. 전체·20대 두 목록을 만든다(관련성·매출·도달률은 연령 공통).
입력: 저장소 data/processed/ (상권 목적 순위, 30분 후보 + 경계, serendipity_v1/serendipity_ranking_v1_2.csv)
출력: <출력 폴더>/hidden_area_combined_top10.csv(추천 목록), hidden_area_combined_metrics.csv(ABC·SERP·결합안 비교)
실행: ~/.venvs/maximus/bin/python 분석/hidden_area_combined_v1.py <저장소>/data/processed/ <출력 폴더>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

P = Path(sys.argv[1])
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
LAM, Q, TOPN, REACH, PM_N, MIN_UNDER = 0.7, 4, 10, 0.5, 20, 7
HOEGI = (37.5898, 127.0579)
PURP = ["공부", "생활서비스", "쇼핑", "식사", "여가문화", "카페"]
TARGET = ["카페", "식사", "쇼핑", "여가문화", "공부"]
AGES = ["전체", "20대"]


def km(lat1, lon1, lat2, lon2):
    return np.hypot((lat1 - lat2) * 111.0, (lon1 - lon2) * 88.2)


def load():
    r = pd.read_csv(P / "commercial_area_purpose_features/official_area_purpose_latest_rankings.csv", dtype={"area_code": str})
    c = pd.read_csv(P / "commercial_area_accessibility/commercial_area_candidates_25pct.csv", dtype={"area_code": str})
    gj = json.loads((P / "commercial_area_accessibility/commercial_area_candidates_25pct.geojson").read_text(encoding="utf-8"))
    cent = {}
    for f in gj["features"]:
        co = f["geometry"]["coordinates"]
        ring = np.array(co[0] if f["geometry"]["type"] == "Polygon" else co[0][0])
        cent[str(f["properties"]["area_code"])] = (ring[:, 1].mean(), ring[:, 0].mean())
    c["lat"] = c.area_code.map(lambda a: cent[a][0])
    c["lon"] = c.area_code.map(lambda a: cent[a][1])
    c["dist_km"] = km(c.lat, c.lon, *HOEGI)
    prof = c.set_index("area_code")[["store_" + p for p in PURP]].fillna(0)
    prof = prof.div(np.linalg.norm(prof.values, axis=1, keepdims=True) + 1e-12, axis=0)
    d = r.merge(c[["area_code", "store_count_total", "sales_amount_total", "dist_km", "lat", "lon"]], on="area_code")
    d["sales_low50"] = d.sales_amount_total.rank(pct=True) <= 0.5
    s = pd.read_csv(P / "serendipity_v1/serendipity_ranking_v1_2.csv", dtype={"area_code": str})
    s = s[["purpose", "age_grp", "area_code", "inertia", "under_months", "peer_ratio", "mmr_rank", "transit_min"]]
    return d, prof, s


def a1(x):
    """경험적 베이즈 수축한 목적 점포 비율과 k (ABC 3단계)."""
    n, N = x.purpose_store_count.fillna(0), x.store_count_total.clip(lower=1)
    m = N >= 30
    p, mu = n[m] / N[m], n[m].sum() / N[m].sum()
    v = np.average((p - mu) ** 2, weights=N[m]) - mu * (1 - mu) * np.mean(1 / N[m])
    k = max(mu * (1 - mu) / max(v, 1e-9) - 1, 1.0)
    return (n + k * mu) / (N + k), k


def mmr_quota(x, rel, prof, pool=60):
    """매출 하위 Q곳 보장 + MMR 재배치 (ABC 4·5단계)."""
    order = rel.sort_values(ascending=False).index
    cand = list(dict.fromkeys(list(order[:pool]) + [i for i in order if x.at[i, "sales_low50"]][:pool]))
    P_ = prof.loc[x.area_code].values
    pos = {i: j for j, i in enumerate(x.index)}

    def sim(i, j):
        dk = km(x.at[i, "lat"], x.at[i, "lon"], x.at[j, "lat"], x.at[j, "lon"])
        return 0.5 * float(P_[pos[i]] @ P_[pos[j]]) + 0.5 * np.exp(-dk / 1.5)

    sel = []
    while len(sel) < min(TOPN, len(cand)):
        need, left = Q - sum(x.at[i, "sales_low50"] for i in sel), TOPN - len(sel)
        pool_ = [i for i in cand if i not in sel and (need < left or x.at[i, "sales_low50"])]
        if not pool_:
            break
        sel.append(max(pool_, key=lambda i: LAM * rel[i] - (1 - LAM) * max([sim(i, j) for j in sel], default=0)))
    return sel


def metrics(t, x_all, pm, label):
    pts = t[["lat", "lon"]].values
    pair = [km(*pts[a], *pts[b]) for a in range(len(pts)) for b in range(a + 1, len(pts))]
    return dict(방법=label, n=len(t), 늘가던곳=int(t.area_code.isin(pm).sum()), 잡음_목적점포5미만=int((t.purpose_store_count < 5).sum()),
                매출하위50=int(t.sales_low50.sum()), 자치구=t.primary_district_name.nunique(),
                상권간평균거리km=round(float(np.mean(pair)), 1) if pair else np.nan, 회기역평균거리km=round(t.dist_km.mean(), 1),
                실제대비동료예상_중앙=round(t.peer_ratio.median(), 2), 덜간달7이상=int((t.under_months >= MIN_UNDER).sum()),
                교통30분이내=int((t.transit_min <= 30).sum()))


def main():
    d, prof, s = load()
    tops, rows = [], []
    for age in AGES:
        sa = s[s.age_grp == age]
        for pu in TARGET:
            x = d[(d.purpose == pu) & (d.mean_period_ratio >= REACH)].merge(sa[sa.purpose == pu], on=["purpose", "area_code"], how="left")
            x.index = x.area_code
            A, k = a1(x)
            x["A1"], x["A1_pct"] = A, A.rank(pct=True)
            pm_abc = set(x.nsmallest(PM_N, "dist_km").area_code) | set(x.nlargest(PM_N, "sales_amount_total").area_code)
            pm_serp = set(x.area_code[x.inertia.astype(str) == "True"])
            pm = pm_abc | pm_serp
            # ABC 그대로 (비교용)
            ya = x[~x.area_code.isin(pm_abc)]
            abc = ya.loc[mmr_quota(ya, ya.A1_pct, prof)]
            # 결합안
            y = x[~x.area_code.isin(pm) & (x.under_months >= MIN_UNDER)]
            comb = y.loc[mmr_quota(y, y.A1_pct, prof)]
            # SERP-v1.2 그대로 (비교용)
            sp = sa[(sa.purpose == pu) & sa.mmr_rank.notna()].sort_values("mmr_rank").head(TOPN).area_code
            serp = d[d.purpose == pu].set_index("area_code").reindex(sp).reset_index() \
                .merge(sa[sa.purpose == pu], on=["purpose", "area_code"], how="left")
            for lab, t in [("ABC", abc), ("SERP-v1.2", serp), ("결합안", comb)]:
                rows.append(dict(연령=age, 목적=pu, k=round(k), 후보=len(y) if lab == "결합안" else len(ya) if lab == "ABC" else np.nan,
                                 결합안과겹침=len(set(t.area_code) & set(comb.area_code)), **metrics(t, x, pm, lab)))
            for rank, (_, a) in enumerate(comb.iterrows(), 1):
                tops.append(dict(연령=age, 목적=pu, 순위=rank, area_code=a.area_code, 상권=a.area_name, 유형=a.area_type_name,
                                 자치구=a.primary_district_name, A1백분위=round(a.A1_pct * 100), 목적점포수=int(a.purpose_store_count),
                                 매출하위50=bool(a.sales_low50), 덜간달=int(a.under_months), 실제대비동료예상=round(a.peer_ratio, 2),
                                 대중교통분=round(a.transit_min, 1), 회기역거리km=round(a.dist_km, 1)))
    OUT.mkdir(parents=True, exist_ok=True)
    m, t = pd.DataFrame(rows), pd.DataFrame(tops)
    m.to_csv(OUT / "hidden_area_combined_metrics.csv", index=False, encoding="utf-8-sig")
    t.to_csv(OUT / "hidden_area_combined_top10.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250)
    print(m.to_string())
    print(t[t.연령 == "전체"].pivot(index="순위", columns="목적", values="상권").to_string())


if __name__ == "__main__":
    main()
