#!/usr/bin/env python3
"""SERP-v1: 동료 출발지 기준 의외성 추천 (동대문구 출발).

SERP-v0와 다른 점
  R(관련성)  목적 매출 예측 → 목적지 선택 모형 예측. 동대문 밖 서울 출발동 120곳으로 학습한 HistGB+교통
             (eval_generalization.py에서 처음 보는 구 NDCG@10 0.78로 검증). "비슷한 조건의 사람이라면 얼마나 갈까"
  U(의외성)  서울 전체 유입 잔차 → 동료 대비 차이. 동대문구민 실제 유입 ÷ 동료 모형 예상 유입(거리·교통·구조 보정 후)
             8개월(2025-12~2026-07) 합으로 계산하고, 덜 간 달이 7달 이상인 곳만 쓴다(안정성 조건)
  관성       실제 유입 상위 20 + 동료보다 3배 넘게 많이 가는 상위권 거점(왕십리형). 추천에서 뺀다
  PATH-v0    순위로 쓰지 않고 목적 필터로만: 여가 v1 기준 PATH 백분위 0.5 이상(그 목적 가게가 충분한 곳)
  그대로     R 하한 0.6, S = R × U, MMR(λ 0.7) 다양성 재배치, 관광특구 추천 제외

목적 ↔ 도착 시간대: 식사=점심·저녁, 카페·쇼핑·공부=오후, 여가문화=심야. 연령: 전체·20대.
v1.1(목적 차별화): R = 동료 예상 백분위 × 목적 가게 비중 백분위, 한 상권은 백분위가 가장 높은 목적 하나에만 배정.
v1.2(기본, 2026-11-16): R = 목적 점수(PATH 여가 v1 정렬판) 백분위로 되돌림. 관련성은 "사용자가 고른 목적에 맞는가"라서.
           동료 예상 유입은 백분위 0.5 이상 하한으로만 쓴다. --v11 이면 예전 판.
변경 기록: 분석/SERP_v1_변경기록.md

실행: ~/.venvs/maximus/bin/python 분석/serendipity_v1.py [--refit]  (--refit: 달별 동료 모형 다시 학습)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_generalization as e  # noqa: E402
from eval_destination_ranking import ndcg_recall  # noqa: E402
from leisure_v1_align import TOURISM_TYPE, build_v1_root  # noqa: E402

serp = e.serp
MONTHS = ["202512", "202601", "202602", "202603", "202604", "202605", "202606", "202607"]
PURPOSE_SLOTS = {"식사": ["점심", "저녁"], "카페": ["오후"], "쇼핑": ["오후"], "공부": ["오후"], "여가문화": ["심야"]}
AGES = ["전체", "20대"]
SMOOTH = 5.0          # 유입 비율 계산 때 더하는 사람 수(작은 상권 과장 방지)
MIN_UNDER_MONTHS = 7  # 8달 중 덜 간 달 수 하한
HUB_RATIO = 3.0       # 동료보다 이만큼 넘게 많이 가는 상위권 = 관성 거점
INERTIA_TOP = 20
R_FLOOR, PATH_FLOOR, TOP_K = 0.6, 0.5, 10
PEER_FLOOR = 0.5  # v1.2: 동료 예상 유입 백분위 하한(다른 동네 사람도 웬만큼은 가는 곳)
V12 = "--v11" not in sys.argv  # 기본 v1.2. --v11이면 예전 판(R = 동료 예상 × 목적 가게 비중)
RANK_FILE = "serendipity_ranking_v1_2.csv" if V12 else "serendipity_ranking_v1_1.csv"
OUT = e.HERE / "데이터/가공/elastic_net"


def month_gap(month: str, ctx) -> tuple[pd.DataFrame, pd.DataFrame]:
    """한 달: 동료 모형 학습 → 동대문 출발 (목적, 연령, 상권)별 실제·예상 유입, 층별 NDCG."""
    xw, alloc, origin_xy, area, static, path = ctx
    codes = static.index.to_numpy()
    panel = pd.read_csv(e.PANEL / f"seoul_od_E_{month}.csv.gz", dtype={"origin": str, "dest": str})
    lab = e.stratum_labels(panel, alloc, codes)
    origins = sorted(set(lab.origin) & set(origin_xy.index))
    test_o = [o for o in origins if origin_xy.at[o, "district"] == "동대문구"]
    pool = [o for o in origins if origin_xy.at[o, "district"] != "동대문구"]
    train_o = list(np.random.default_rng(0).choice(pool, size=e.N_TRAIN_ORIGINS, replace=False))
    pop = lab[lab.origin.isin(pool) & (lab.age_grp == "전체")].groupby("area_code")["y"].sum()
    tr = e.long_table(lab, train_o, codes, origin_xy, area, alloc)
    te = e.long_table(lab, test_o, codes, origin_xy, area, alloc)
    adist = area.set_index("area_code").primary_district_name

    def feats(df):  # 같은 구 변수: 누구나 자기 구에 더 머문다 → 이걸 빼야 U가 '구 밖이면 의외'로 쏠리지 않는다
        X = e.features(df, static, path, pop, True)
        X["같은 구"] = (df.origin.map(origin_xy.district).to_numpy() == df.area_code.map(adist).to_numpy()).astype(float)
        return X

    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0)
    m.fit(feats(tr), np.log1p(tr.y.to_numpy()))
    te["pred"] = np.expm1(m.predict(feats(te))).clip(min=0)

    ev = []
    for (o, s, a), idx in te.groupby(["origin", "slot", "age_grp"]).indices.items():
        g = te.iloc[idx]
        if g.y.sum() > 0:
            ev.append({"month": month, "origin": o, "slot": s, "age_grp": a,
                       "ndcg10": ndcg_recall(g.y.to_numpy(), g.pred.to_numpy())[0],
                       "ndcg10_거리순": ndcg_recall(g.y.to_numpy(), -g.dist_km.to_numpy())[0]})
    # 층마다 예상 분포를 실제 총량에 맞춘다 → '얼마나 많이'가 아니라 '어디로'만 비교
    key = ["origin", "slot", "age_grp"]
    te["exp"] = te.pred / te.groupby(key).pred.transform("sum").replace(0, np.nan) * te.groupby(key).y.transform("sum")
    rows = []
    for pur, slots in PURPOSE_SLOTS.items():
        sub = te[te.slot.isin(slots)]
        agg = sub.groupby(["age_grp", "area_code"], as_index=False).agg(act=("y", "sum"), exp=("exp", "sum"))
        rows.append(agg.assign(purpose=pur))
    out = pd.concat(rows).assign(month=month)
    out["log_ratio"] = np.log((out.act + SMOOTH) / (out.exp.fillna(0) + SMOOTH))
    print(month, "동대문 NDCG@10", round(pd.DataFrame(ev).ndcg10.mean(), 3), flush=True)
    return out, pd.DataFrame(ev)


def score_purpose(g: pd.DataFrame, area: pd.DataFrame, path_v1: pd.DataFrame, pur: str) -> pd.DataFrame:
    """목적 하나의 R·U·자격. MMR은 목적 배정(assign_purposes) 뒤에 한다."""
    g = g.merge(area, on="area_code", how="inner").reset_index(drop=True)
    g["path_pct"] = serp.pct_rank(g.area_code.map(path_v1[pur]).fillna(0))
    # v1.1: 카페·쇼핑·공부는 같은 오후 시간대라 동료 예상(exp)이 똑같다 → 목적 특화도(그 목적 가게 비중 백분위)를 곱해 R을 목적별로 가른다
    g["r_flow"] = serp.pct_rank(g.exp)
    g["purpose_fit"] = serp.pct_rank(g[f"share_{pur}"].fillna(0))
    if V12:  # v1.2: 관련성 = 사용자가 고른 목적에 맞는 정도(목적 점수 백분위). 동료 예상은 '갈 만한 곳' 하한으로만
        g["relevance"] = g.path_pct
    else:
        g["relevance"] = serp.pct_rank(g.r_flow * g.purpose_fit)
    g["peer_ratio"] = np.exp(g.gap)
    g["unexpectedness"] = serp.pct_rank(-g.gap)
    act_rank = g.act.rank(ascending=False, method="first")
    g["inertia"] = (act_rank <= INERTIA_TOP) | ((g.peer_ratio > HUB_RATIO) & (act_rank <= 0.05 * len(g)))
    gate = (g.r_flow >= PEER_FLOOR) if V12 else (g.relevance >= R_FLOOR)
    g["eligible"] = (gate & (g.path_pct >= PATH_FLOOR) & ~g.inertia
                     & (g.under_months >= MIN_UNDER_MONTHS) & (g.area_type_name != TOURISM_TYPE))
    g["serendipity_score"] = (g.relevance * g.unexpectedness).where(g.eligible)
    g["score_pct"] = g.serendipity_score.rank(pct=True)  # 목적 안 자격 후보 사이 백분위
    g["reason"] = [f"{pur} 목적 점수 상위 {1 - f:.0%} · 비슷한 조건 동료 기준 예상의 {r:.2f}배만 감 · {u}/8달 덜 감 · 대중교통 {t:.0f}분"
                   for r, u, t, f in zip(g.peer_ratio, g.under_months, g.transit_min, g.path_pct)]
    return g


def assign_purposes(full: pd.DataFrame) -> pd.DataFrame:
    """v1.1 목적 배정: 한 상권은 (연령층마다) 목적 안 백분위가 가장 높은 목적 하나에서만 추천한다. 그 뒤 목적별 MMR."""
    full = full.copy()
    best = full[full.eligible].sort_values("score_pct", ascending=False).drop_duplicates(["age_grp", "area_code"])
    key = set(zip(best.age_grp, best.area_code, best.purpose))
    full["assigned"] = [k in key for k in zip(full.age_grp, full.area_code, full.purpose)]
    full["mmr_rank"] = np.nan
    full["score_rank"] = np.nan
    out = []
    for _, g in full.groupby(["purpose", "age_grp"]):
        g = g.reset_index(drop=True)
        s = g.serendipity_score.where(g.assigned)
        g["score_rank"] = s.rank(ascending=False, method="first")
        order = serp.mmr_rerank(g.assign(_s=s), "_s", TOP_K * 2, 0.7, 1.5)
        g.loc[order, "mmr_rank"] = np.arange(1, len(order) + 1)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def main() -> None:
    ctx = e.load_common()
    xw, alloc, origin_xy, *_ = ctx
    # 달별 동료 모형 결과는 저장해 두고 다시 쓴다(8달 학습 약 8분). 모형을 바꿨으면 --refit
    gap_f, ev_f = OUT / "serp_v1_monthly_gap.csv", OUT / "serp_v1_r_ndcg_by_month.csv"
    if gap_f.exists() and ev_f.exists() and "--refit" not in sys.argv:
        monthly = pd.read_csv(gap_f, dtype={"area_code": str, "month": str})
        ev = pd.read_csv(ev_f, dtype={"month": str})
    else:
        parts = [month_gap(m, ctx) for m in MONTHS]
        monthly = pd.concat([p[0] for p in parts])
        ev = pd.concat([p[1] for p in parts])
        monthly.to_csv(gap_f, index=False, encoding="utf-8-sig")
        ev.to_csv(ev_f, index=False, encoding="utf-8-sig")

    # 8달 합 + 안정성
    k = ["purpose", "age_grp", "area_code"]
    tot = monthly.groupby(k, as_index=False).agg(act=("act", "sum"), exp=("exp", "sum"),
                                                 under_months=("log_ratio", lambda s: int((s < 0).sum())))
    tot["gap"] = np.log((tot.act + SMOOTH) / (tot.exp + SMOOTH))
    piv = monthly[(monthly.purpose == "식사") & (monthly.age_grp == "전체")].pivot(index="area_code", columns="month", values="log_ratio")
    corr = piv.corr(method="spearman").to_numpy()
    print(f"U 안정성(식사·전체): 달 간 잔차 순위상관 평균 {corr[np.triu_indices_from(corr, 1)].mean():.3f}, "
          f"최소 {corr[np.triu_indices_from(corr, 1)].min():.3f}")

    # 동대문 출발동 평균 교통시간
    tt = pd.read_csv(e.TRANSIT, dtype={"origin": str, "area_code": str})
    ddm_o = origin_xy.index[origin_xy.district == "동대문구"]
    tt = tt[tt.origin.isin(ddm_o)].groupby("area_code").transit_min.mean()

    v1 = build_v1_root()
    area, purpose = serp.load_inputs(v1, 20254, use_movement=True)
    path_v1 = purpose.pivot(index="area_code", columns="purpose", values="path_v0_score")
    area = area.assign(transit_min=area.area_code.map(tt))  # dist_km = 동대문구 상권 중심에서 직선거리

    out = []
    for (pur, age), g in tot.groupby(["purpose", "age_grp"]):
        out.append(score_purpose(g, area, path_v1, pur).assign(purpose=pur, age_grp=age))
    full = assign_purposes(pd.concat(out, ignore_index=True))
    cols = ["purpose", "age_grp", "mmr_rank", "score_rank", "area_code", "area_name", "primary_district_name", "area_type_name",
            "serendipity_score", "relevance", "r_flow", "purpose_fit", "unexpectedness", "peer_ratio", "under_months", "act", "exp",
            "path_pct", "transit_min", "dist_km", "inertia", "eligible", "assigned", "reason"]
    full = full.sort_values(["purpose", "age_grp", "mmr_rank", "score_rank"], na_position="last")
    full[cols].to_csv(OUT / RANK_FILE, index=False, encoding="utf-8-sig")
    print("판:", "v1.2 (R=목적 점수)" if V12 else "v1.1", "→", RANK_FILE)

    print("\nR(동료 모형) 동대문 NDCG@10 8달:", ev.groupby("month").ndcg10.mean().round(3).to_dict(),
          "| 거리순", round(ev.ndcg10_거리순.mean(), 3))
    print("후보 수(eligible):", full.groupby(["purpose", "age_grp"]).eligible.sum().to_dict())
    print("관성 거점(동료 대비 3배+):", full[full.inertia & (full.peer_ratio > HUB_RATIO) & (full.age_grp == "전체")]
          .groupby("area_name").peer_ratio.max().sort_values(ascending=False).head(8).round(1).to_dict())
    for (pur, age), g in full[full.mmr_rank.notna()].groupby(["purpose", "age_grp"]):
        g = g.nsmallest(TOP_K, "mmr_rank")
        print(f"\n[{pur}·{age}]", ", ".join(f"{n}({r:.2f}배·{t:.0f}분)" for n, r, t in zip(g.area_name, g.peer_ratio, g.transit_min)))

    # 목적 간 상위 10 겹침(v1.0은 쇼핑-카페 9/10)
    for age in AGES:
        t = {p: set(g[g.mmr_rank <= TOP_K].area_code) for p, g in full[full.age_grp == age].groupby("purpose")}
        print(f"목적 간 겹침({age}):", sum(len(t[a] & t[b]) for a in t for b in t if a < b), "건",
              "| 목적별 상위 10 수:", {p: len(v) for p, v in t.items()})

    # 이전 판(EN·동대문 OD·여가 v1)과 겹침, 실제 유입 순위
    old = pd.read_csv(OUT / "serendipity_ranking_en_ddm_v1.csv", dtype={"area_code": str})
    for pur in PURPOSE_SLOTS:
        a = set(full[(full.purpose == pur) & (full.age_grp == "전체") & (full.mmr_rank <= TOP_K)].area_code)
        b = set(old[(old.purpose == pur) & (old.mmr_rank <= TOP_K)].area_code)
        g = full[(full.purpose == pur) & (full.age_grp == "전체")]
        r = g.act.rank(ascending=False)[g.area_code.isin(a)].median()
        print(f"{pur}: EN판과 겹침 {len(a & b)}/10, v1 상위10 실제 유입 순위 중앙값 {r:.0f}/{len(g)}")


if __name__ == "__main__":
    main()
