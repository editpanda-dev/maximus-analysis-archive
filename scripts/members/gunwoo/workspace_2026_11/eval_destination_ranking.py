#!/usr/bin/env python3
"""동대문구 출발 목적지 랭킹 평가 (시간 순 분할, 기준선 대비 NDCG@10·Recall@10).

정답: 서울 생활이동 OD의 '도착=기타 장소(E)' 이동을 상권(786곳)에 겹침 비율로 나눈 실제 유입.
층(choice stratum): 출발동(동대문구 통계동 14개) × 도착 시간대 × 연령(전체·20대). 같은 동 안 이동은 뺀다.
  시간대 → 비교용 목적: 점심 11~13시=식사, 오후 14~16시=카페, 저녁 17~20시=식사, 심야 21~23시=여가문화

분할: 시험 달 T를 맞힌다. 과거 = T보다 앞선 달(3월부터).
  모형 학습은 한 달 앞으로 당겨서: 목표 T-1, 과거 = T-1보다 앞선 달. 미래 정보는 안 쓴다.

비교
  거리순: 출발동 중심(겹친 상권 중심의 면적 가중 평균)에서 가까운 순
  인기순: PATH-v0(시간대 목적, 공식 저장소 2025 4분기 점수)
  과거 유입순(층): 같은 출발동·시간대·연령의 과거 월평균 유입
  과거 유입순(동대문 전체): 동대문구 전체 과거 월평균 유입(모든 층 같은 목록)
  EN: ElasticNetCV(로그 유입 ~ 로그 거리 + 구조 변수 + PATH + 과거 유입 2종)
  EN-구조만: 과거 유입 없이(처음 보는 상권·새 출발지 상황)
  HistGB: EN과 같은 변수

실행: ~/.venvs/maximus/bin/python 분석/eval_destination_ranking.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNetCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)
HERE = Path(__file__).resolve().parents[1]
REPO = HERE / "maximus-analysis-archive"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_serendipity_ranking as serp  # noqa: E402
from build_dongdaemun_od_inflow import stat_to_admin  # noqa: E402
from elastic_net_v0 import L1_GRID, base_features, extra_features  # noqa: E402

PANEL = HERE / "데이터/가공/od_eval"
SLOTS = {"점심": ([11, 12, 13], "식사"), "오후": ([14, 15, 16], "카페"),
         "저녁": ([17, 18, 19, 20], "식사"), "심야": ([21, 22, 23], "여가문화")}
AGES = {"전체": None, "20대": [20, 25]}
K = 10
MASK_FILL = 2.0


# ---------------------------------------------------------------------------
# 정답 만들기
# ---------------------------------------------------------------------------

def dong_to_area(xw: pd.DataFrame, ov: pd.DataFrame) -> pd.DataFrame:
    """통계동 → 상권 배분 가중치(stat_code, area_code, w)."""
    o = ov[["area_code", "admin_code", "overlap_share"]].copy()
    o["w_area"] = o["overlap_share"] / o.groupby("admin_code")["overlap_share"].transform("sum")
    m = xw.dropna(subset=["admin_code"]).merge(o, on="admin_code")
    m["w"] = m["weight"] * m["w_area"]
    return m.groupby(["stat_code", "area_code"], as_index=False)["w"].sum()


def month_labels(month: str, alloc: pd.DataFrame) -> pd.DataFrame:
    """(month, origin, slot, age_grp, area_code, y)."""
    d = pd.read_csv(PANEL / f"ddm_od_E_{month}.csv", dtype={"origin": str, "dest": str, "month": str})
    d = d[d["origin"] != d["dest"]]
    d["v"] = d["cnt"] + MASK_FILL * d["masked"]
    out = []
    for slot, (hours, _) in SLOTS.items():
        s = d[d["hour"].isin(hours)]
        for ag, ages in AGES.items():
            a = s if ages is None else s[s["age"].isin(ages)]
            g = a.groupby(["origin", "dest"], as_index=False)["v"].sum()
            g = g.merge(alloc, left_on="dest", right_on="stat_code")
            g["y"] = g["v"] * g["w"]
            g = g.groupby(["origin", "area_code"], as_index=False)["y"].sum()
            out.append(g.assign(slot=slot, age_grp=ag))
    return pd.concat(out).assign(month=month)


# ---------------------------------------------------------------------------
# 평가 지표
# ---------------------------------------------------------------------------

def ndcg_recall(y: np.ndarray, s: np.ndarray, k: int = K) -> tuple[float, float]:
    order = np.argsort(-s, kind="stable")[:k]
    ideal = np.sort(y)[::-1][:k]
    disc = 1 / np.log2(np.arange(2, k + 2))
    idcg = (ideal * disc).sum()
    ndcg = (y[order] * disc).sum() / idcg if idcg > 0 else np.nan
    true_top = set(np.argsort(-y, kind="stable")[:k])
    return ndcg, len(true_top & set(order)) / k


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main() -> None:
    months = sorted(p.stem.split("_")[-1] for p in PANEL.glob("ddm_od_E_*.csv"))
    print("months", months)
    xw, ov = stat_to_admin()
    alloc = dong_to_area(xw, ov)

    area, purpose = serp.load_inputs(REPO, 20254, use_movement=True)
    area = area.reset_index(drop=True)
    codes = area["area_code"].to_numpy()
    static = pd.concat([base_features(area), extra_features(area)], axis=1).drop(columns=["동대문거리_km"])
    static.index = codes
    path = purpose.pivot(index="area_code", columns="purpose", values="path_v0_score").reindex(codes).fillna(0)

    # 출발동 중심: 그 동(들)에 겹친 상권 중심의 겹침 면적 가중 평균
    o = ov.merge(area[["area_code", "lat", "lon"]], on="area_code")
    oc = xw[xw["stat_code"].str.startswith("11060")].merge(o, on="admin_code")
    oc["ww"] = oc["weight"] * oc["overlap_m2"]
    origin_xy = oc.groupby("stat_code").apply(
        lambda g: pd.Series({"lat": np.average(g.lat, weights=g.ww), "lon": np.average(g.lon, weights=g.ww)}))

    lab = pd.concat([month_labels(m, alloc) for m in months])
    lab = lab[lab["area_code"].isin(codes)]
    strata = lab[["origin", "slot", "age_grp"]].drop_duplicates()
    strata = strata[strata["origin"].isin(origin_xy.index)]
    key = ["origin", "slot", "age_grp", "area_code"]
    full = strata.merge(pd.DataFrame({"area_code": codes}), how="cross")
    wide = lab.pivot_table(index=key, columns="month", values="y", aggfunc="sum").reset_index()
    full = full.merge(wide, on=key, how="left").fillna({m: 0.0 for m in months})
    xy = area.set_index("area_code")[["lat", "lon"]]
    full["dist_km"] = serp.haversine_km(origin_xy.loc[full.origin, "lat"].to_numpy(), origin_xy.loc[full.origin, "lon"].to_numpy(),
                                        xy.loc[full.area_code, "lat"].to_numpy(), xy.loc[full.area_code, "lon"].to_numpy())
    full["path"] = [path.at[a, SLOTS[s][1]] for a, s in zip(full.area_code, full.slot)]
    print("층", len(strata), "행", len(full))

    def feats(df: pd.DataFrame, hist: list[str], with_lag: bool) -> pd.DataFrame:
        X = static.loc[df.area_code].reset_index(drop=True).copy()
        X["log_거리"] = np.log(df["dist_km"].clip(lower=0.3)).to_numpy()
        X["PATH"] = df["path"].to_numpy()
        for s in SLOTS:
            X["슬롯_" + s] = (df["slot"] == s).to_numpy(float)
        X["20대"] = (df["age_grp"] == "20대").to_numpy(float)
        if with_lag:
            X["log_과거유입_층"] = np.log1p(df[hist].mean(axis=1)).to_numpy()
            X["log_과거유입_동대문"] = np.log1p(df["ddm_hist"]).to_numpy()
        return X

    def add_ddm_hist(df: pd.DataFrame, hist: list[str]) -> pd.DataFrame:
        tot = df[df.age_grp == "전체"].groupby("area_code")[hist].sum().mean(axis=1)
        return df.assign(ddm_hist=df["area_code"].map(tot).to_numpy())

    rows, coef_rows = [], []
    for T in months:
        i = months.index(T)
        if i < 2:
            continue  # 학습에 과거 1달 + 목표 1달이 필요
        hist_te, tgt_tr, hist_tr = months[:i], months[i - 1], months[:i - 1]
        te, tr = add_ddm_hist(full, hist_te), add_ddm_hist(full, hist_tr)
        scores = {
            "거리순": -te["dist_km"].to_numpy(),
            "인기순(PATH-v0)": te["path"].to_numpy(),
            "과거유입(층)": te[hist_te].mean(axis=1).to_numpy(),
            "과거유입(동대문 전체)": te["ddm_hist"].to_numpy(),
        }
        ytr = np.log1p(tr[tgt_tr].to_numpy())
        groups = tr["origin"].to_numpy()
        for name, lagged in [("EN", True), ("EN-구조만", False)]:
            Xtr, Xte = feats(tr, hist_tr, lagged), feats(te, hist_te, lagged)
            splits = list(GroupKFold(5).split(Xtr, ytr, groups))  # 출발동 단위로 접어 alpha를 고른다
            m = make_pipeline(StandardScaler(), ElasticNetCV(l1_ratio=L1_GRID, alphas=40, max_iter=5000,
                                                             cv=splits, n_jobs=-1))
            m.fit(Xtr, ytr)
            scores[name] = m.predict(Xte)
            en = m[-1]
            coef_rows += [{"test_month": T, "model": name, "feature": f, "coef": c, "alpha": en.alpha_, "l1_ratio": en.l1_ratio_}
                          for f, c in zip(Xtr.columns, en.coef_)]
        Xtr, Xte = feats(tr, hist_tr, True), feats(te, hist_te, True)
        scores["HistGB"] = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0).fit(Xtr, ytr).predict(Xte)

        for (o_, s_, a_), idx in te.groupby(["origin", "slot", "age_grp"]).indices.items():
            y = te[T].to_numpy()[idx]
            if y.sum() <= 0:
                continue
            for name, sc in scores.items():
                n, r = ndcg_recall(y, sc[idx])
                rows.append({"test_month": T, "origin": o_, "slot": s_, "age_grp": a_, "model": name, "ndcg10": n, "recall10": r})
        print("done", T)

    res = pd.DataFrame(rows)
    res.to_csv(PANEL / "eval_by_stratum.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(coef_rows).to_csv(PANEL / "eval_en_coefficients.csv", index=False, encoding="utf-8-sig")
    summ = res.groupby(["test_month", "model"])[["ndcg10", "recall10"]].mean().round(3).unstack(0)
    print(summ.sort_values(summ.columns[-2], ascending=False).to_string())
    by_slot = res.groupby(["slot", "model"])["ndcg10"].mean().round(3).unstack(0)
    print(by_slot.to_string())
    summ.to_csv(PANEL / "eval_summary.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
