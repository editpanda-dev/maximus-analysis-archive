#!/usr/bin/env python3
"""일반화 평가: 서울 다른 출발지로 학습한 모형이 처음 보는 구(동대문구 등)의 행선지 순위를 맞히나.

정답: 서울 생활이동 OD 2026-06, 도착=기타 장소(E). 같은 동 안 이동 제외. 후보 = 공식 상권 786곳.
층: 출발동 × 도착 시간대(점심·오후·저녁·심야) × 연령(전체·20대).
분할: 시험 구 하나를 통째로 뺀다(출발지 기준). 학습은 나머지 구 출발동 중 표본 120개.
  → 시험 구의 과거 유입은 어디에도 안 쓰므로 '과거값 복사'가 불가능하다.

비교
  거리순 / 인기순(PATH-v0, 시간대 목적) / 타 출발지 인기순(학습 출발지들의 상권별 유입 합)
  EN-구조만: 거리 + 상권 구조 + PATH (+ 시간대·연령·거리 상호작용)
  EN: EN-구조만 + 타 출발지 인기
  HistGB: EN과 같은 변수
상권의 동대문 기준 도달률 변수는 출발지마다 의미가 달라 뺀다.

실행: ~/.venvs/maximus/bin/python 분석/eval_generalization.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import geopandas as gpd
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
from elastic_net_v0 import base_features, extra_features  # noqa: E402
from eval_destination_ranking import K, SLOTS, dong_to_area, ndcg_recall  # noqa: E402

PANEL = HERE / "데이터/가공/od_eval"
MONTH = "202606"
TEST_DISTRICTS = ["동대문구", "성북구", "광진구", "마포구", "관악구", "강남구"]
N_TRAIN_ORIGINS = 120
MASK_FILL = 2.0
TRANSIT = PANEL / "transit_time_origin_area.csv"  # build_transit_time_matrix.py. 있으면 교통 변수 모형을 같이 돌린다
TRANSIT_CAP = 90
DDM_SPECIFIC = ["동대문거리_km", "30분도달률", "log_도달률", "도달률_08시", "도달률_14시", "도달률_19시"]


# ---------------------------------------------------------------------------
# 공통 입력 (학생 분석 스크립트도 씀)
# ---------------------------------------------------------------------------

def area_centroids() -> pd.DataFrame:
    """서울 상권 1,650곳 중심(위경도). 원천 shp 그대로."""
    g = gpd.read_file(f"zip://{REPO / 'data/raw/commercial_area/commercial_area.zip'}")
    c = g.centroid.to_crs(4326)  # 원천 좌표계 EPSG:5181(미터)에서 중심 계산
    return pd.DataFrame({"area_code": g["TRDAR_CD"].astype(str), "lat": c.y, "lon": c.x})


def load_common():
    xw, ov = stat_to_admin()
    alloc = dong_to_area(xw, ov)
    cent = area_centroids()
    o = ov[["area_code", "admin_code", "overlap_m2"]].merge(cent, on="area_code")
    oc = xw.dropna(subset=["admin_code"]).merge(o, on="admin_code")
    oc["ww"] = oc["weight"] * oc["overlap_m2"]
    origin_xy = oc.groupby("stat_code").apply(
        lambda g: pd.Series({"lat": np.average(g.lat, weights=g.ww), "lon": np.average(g.lon, weights=g.ww),
                             "district": g.district.iloc[0], "name": g.admin_name.iloc[0]}))
    area, purpose = serp.load_inputs(REPO, 20254, use_movement=True)
    area = area.reset_index(drop=True)
    static = pd.concat([base_features(area), extra_features(area)], axis=1).drop(columns=DDM_SPECIFIC)
    static.index = area["area_code"].to_numpy()
    path = purpose.pivot(index="area_code", columns="purpose", values="path_v0_score").reindex(static.index).fillna(0)
    return xw, alloc, origin_xy, area, static, path


def stratum_labels(panel: pd.DataFrame, alloc: pd.DataFrame, codes, by_age=True) -> pd.DataFrame:
    """패널 → (origin, slot, age_grp, area_code, y). 같은 동 안 이동 제외, '*'=2명."""
    d = panel[(panel["origin"] != panel["dest"]) & panel["slot"].isin(list(SLOTS))].copy()
    d["v"] = d["cnt"] + MASK_FILL * d["masked"]
    parts = [d.assign(age_grp="전체")]
    if by_age:
        parts.append(d[d["age20"] == 1].assign(age_grp="20대"))
    d = pd.concat(parts).groupby(["origin", "dest", "slot", "age_grp"], as_index=False)["v"].sum()
    d = d.merge(alloc, left_on="dest", right_on="stat_code")
    d["y"] = d["v"] * d["w"]
    d = d[d["area_code"].isin(codes)]
    return d.groupby(["origin", "slot", "age_grp", "area_code"], as_index=False)["y"].sum()


def long_table(lab: pd.DataFrame, origins, codes, origin_xy, area, alloc: pd.DataFrame) -> pd.DataFrame:
    """층 × 후보 상권. 출발동에 걸친 상권은 그 출발지 후보에서 뺀다(같은 동 안 이동을 정답에서 뺐으므로)."""
    strata = lab[lab["origin"].isin(origins)][["origin", "slot", "age_grp"]].drop_duplicates()
    full = strata.merge(pd.DataFrame({"area_code": codes}), how="cross")
    own = alloc[alloc["w"] > 0][["stat_code", "area_code"]].rename(columns={"stat_code": "origin"}).assign(_own=1)
    full = full.merge(own, on=["origin", "area_code"], how="left")
    full = full[full["_own"].isna()].drop(columns="_own")
    full = full.merge(lab, on=["origin", "slot", "age_grp", "area_code"], how="left").fillna({"y": 0.0})
    xy = area.set_index("area_code")[["lat", "lon"]]
    full["dist_km"] = serp.haversine_km(origin_xy.loc[full.origin, "lat"].to_numpy(), origin_xy.loc[full.origin, "lon"].to_numpy(),
                                        xy.loc[full.area_code, "lat"].to_numpy(), xy.loc[full.area_code, "lon"].to_numpy())
    if TRANSIT.exists():
        tt = pd.read_csv(TRANSIT, dtype={"origin": str, "area_code": str})[["origin", "area_code", "transit_min"]]
        full = full.merge(tt, on=["origin", "area_code"], how="left")
        full["transit_min"] = full["transit_min"].fillna(TRANSIT_CAP)
    return full


def features(df: pd.DataFrame, static, path, pop: pd.Series | None, transit: bool = False) -> pd.DataFrame:
    X = static.loc[df.area_code].reset_index(drop=True).copy()
    ld = np.log(df["dist_km"].clip(lower=0.3)).to_numpy()
    X["log_거리"] = ld
    X["log_거리²"] = ld ** 2
    X["PATH"] = [path.at[a, SLOTS[s][1]] for a, s in zip(df.area_code, df.slot)]
    for s in SLOTS:
        X["슬롯_" + s] = (df["slot"] == s).to_numpy(float)
        X["log_거리×" + s] = ld * X["슬롯_" + s]
    X["20대"] = (df["age_grp"] == "20대").to_numpy(float)
    X["log_거리×20대"] = ld * X["20대"]
    if pop is not None:
        X["log_타출발지인기"] = np.log1p(df["area_code"].map(pop).fillna(0)).to_numpy()
    if transit:
        lt = np.log(df["transit_min"].clip(lower=3)).to_numpy()
        X["log_교통시간"] = lt
        X["log_교통시간²"] = lt ** 2
        X["교통/직선 비"] = (df["transit_min"] / df["dist_km"].clip(lower=0.3)).to_numpy()  # 1km에 몇 분: 철도 직결이면 작다
        for s in SLOTS:
            X["log_교통시간×" + s] = lt * X["슬롯_" + s]
        X["log_교통시간×20대"] = lt * X["20대"]
    return X


def fit_en(X, y, groups):
    splits = list(GroupKFold(5).split(X, y, groups))
    return make_pipeline(StandardScaler(), ElasticNetCV(l1_ratio=[0.5, 0.9, 1.0], alphas=20, max_iter=3000,
                                                        cv=splits, n_jobs=-1)).fit(X, y)


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main() -> None:
    # 인자: [달] [시험 구 ...]  예) 202603 동대문구 성북구
    month = sys.argv[1] if len(sys.argv) > 1 else MONTH
    test_districts = sys.argv[2:] or TEST_DISTRICTS
    xw, alloc, origin_xy, area, static, path = load_common()
    codes = static.index.to_numpy()
    panel = pd.read_csv(PANEL / f"seoul_od_E_{month}.csv.gz", dtype={"origin": str, "dest": str})
    lab = stratum_labels(panel, alloc, codes)
    origins = sorted(set(lab.origin) & set(origin_xy.index))
    print(month, "출발동", len(origins), "/ 상권", len(codes))
    rng = np.random.default_rng(0)
    rows, coefs = [], []
    for dist_name in test_districts:
        test_o = [o for o in origins if origin_xy.at[o, "district"] == dist_name]
        pool = [o for o in origins if origin_xy.at[o, "district"] != dist_name]
        train_o = list(rng.choice(pool, size=min(N_TRAIN_ORIGINS, len(pool)), replace=False))
        pop = lab[lab.origin.isin(pool) & (lab.age_grp == "전체")].groupby("area_code")["y"].sum()
        tr, te = long_table(lab, train_o, codes, origin_xy, area, alloc), long_table(lab, test_o, codes, origin_xy, area, alloc)
        ytr, g = np.log1p(tr["y"].to_numpy()), tr["origin"].to_numpy()
        scores = {"거리순": -te["dist_km"].to_numpy(),
                  "인기순(PATH-v0)": [path.at[a, SLOTS[s][1]] for a, s in zip(te.area_code, te.slot)],
                  "타 출발지 인기순": te["area_code"].map(pop).fillna(0).to_numpy()}
        has_tt = "transit_min" in te
        if has_tt:
            scores["교통시간순"] = -te["transit_min"].to_numpy()
        variants = [("EN-구조만", None, False), ("EN", pop, False)]
        if has_tt:
            variants += [("EN-구조만+교통", None, True), ("EN+교통", pop, True)]
        for name, p, tt in variants:
            Xtr, Xte = features(tr, static, path, p, tt), features(te, static, path, p, tt)
            m = fit_en(Xtr, ytr, g)
            scores[name] = m.predict(Xte)
            coefs += [{"test_district": dist_name, "model": name, "feature": f, "coef": c} for f, c in zip(Xtr.columns, m[-1].coef_)]
        for name, tt in [("HistGB", False)] + ([("HistGB+교통", True)] if has_tt else []):
            Xtr, Xte = features(tr, static, path, pop, tt), features(te, static, path, pop, tt)
            scores[name] = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0).fit(Xtr, ytr).predict(Xte)
        for (o_, s_, a_), idx in te.groupby(["origin", "slot", "age_grp"]).indices.items():
            y = te["y"].to_numpy()[idx]
            if y.sum() <= 0:
                continue
            for name, sc in scores.items():
                n, r = ndcg_recall(y, np.asarray(sc, float)[idx])
                rows.append({"test_district": dist_name, "origin": o_, "slot": s_, "age_grp": a_, "model": name,
                             "ndcg10": n, "recall10": r})
        print("done", dist_name, len(test_o), "개 동")
    res = pd.DataFrame(rows).assign(month=month)
    sfx = "" if month == MONTH and not sys.argv[2:] else f"_{month}"
    res.to_csv(PANEL / f"gen_eval_by_stratum{sfx}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(coefs).to_csv(PANEL / f"gen_eval_en_coefficients{sfx}.csv", index=False, encoding="utf-8-sig")
    summ = res.groupby(["model", "test_district"])["ndcg10"].mean().unstack().round(3)
    summ["평균"] = summ.mean(axis=1).round(3)
    print(summ.sort_values("평균", ascending=False).to_string())
    print(res.groupby(["model", "test_district"])["recall10"].mean().unstack().round(3).to_string())
    print(res[res.test_district == "동대문구"].groupby(["model", "age_grp"])["ndcg10"].mean().unstack().round(3).to_string())
    summ.to_csv(PANEL / f"gen_eval_summary{sfx}.csv", encoding="utf-8-sig")


if __name__ == "__main__":
    main()
