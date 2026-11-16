#!/usr/bin/env python3
"""SERP-v1 후속 점검 (2026-11-16).

1. 시간대 단계별 점수: 추천을 대중교통 ≤10분 / 10~20분 / 20~30분 단계 안에서 하면 PATH-v0·거리순·동료 모형의 NDCG가 어떻게 되나
2. 동료 모형 고르기: HistGB(log, 현행) · HistGB(Poisson 손실) · Elastic Net · Poisson GLM을 같은 구 홀드아웃으로 비교.
   U = 실제 ÷ 예상이므로 순위(NDCG)뿐 아니라 상권별 예상 총량이 실제와 얼마나 맞는지(보정)도 본다
3. (serendipity_v1.py v1.2로 반영됨: 관련성 = 목적 점수)
4. 대학생 검증: 성북구 대학(고려대·성신여대·동덕여대·국민대·한성대 등)을 학습에서 빼도 '우리 학생은 성북을 덜 간다'가 남나

실행: ~/.venvs/maximus/bin/python 분석/serp_v1_followup.py [1 4]
출력: 데이터/가공/elastic_net/followup/*.csv
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_generalization as e  # noqa: E402
from eval_destination_ranking import ndcg_recall  # noqa: E402
from student_flows import campus_dongs, student_labels  # noqa: E402

warnings.filterwarnings("ignore", category=ConvergenceWarning)
OUT = e.HERE / "데이터/가공/elastic_net/followup"
MONTH = "202606"
BANDS = [("10분 이내", 0, 10), ("10~20분", 10, 20), ("20~30분", 20, 30)]
K_BAND = 5


def ndcg_at(y, s, k):
    y, s = np.asarray(y, float), np.asarray(s, float)
    order = np.argsort(-s)[:k]
    gains = (2 ** np.log1p(y)) - 1  # 유입 수 차이가 너무 크지 않게 log 이득
    dcg = (gains[order] / np.log2(np.arange(2, len(order) + 2))).sum()
    ideal = np.sort(gains)[::-1][:k]
    idcg = (ideal / np.log2(np.arange(2, len(ideal) + 2))).sum()
    return dcg / idcg if idcg > 0 else np.nan


def setup(month, test_district, ctx):
    xw, alloc, origin_xy, area, static, path = ctx
    codes = static.index.to_numpy()
    panel = pd.read_csv(e.PANEL / f"seoul_od_E_{month}.csv.gz", dtype={"origin": str, "dest": str})
    lab = e.stratum_labels(panel, alloc, codes)
    origins = sorted(set(lab.origin) & set(origin_xy.index))
    test_o = [o for o in origins if origin_xy.at[o, "district"] == test_district]
    pool = [o for o in origins if origin_xy.at[o, "district"] != test_district]
    train_o = list(np.random.default_rng(0).choice(pool, size=e.N_TRAIN_ORIGINS, replace=False))
    pop = lab[lab.origin.isin(pool) & (lab.age_grp == "전체")].groupby("area_code")["y"].sum()
    tr = e.long_table(lab, train_o, codes, origin_xy, area, alloc)
    te = e.long_table(lab, test_o, codes, origin_xy, area, alloc)
    adist = area.set_index("area_code").primary_district_name

    def feats(df):
        X = e.features(df, static, path, pop, True)
        X["같은 구"] = (df.origin.map(origin_xy.district).to_numpy() == df.area_code.map(adist).to_numpy()).astype(float)
        return X

    return tr, te, feats(tr), feats(te), path


def fit_models(tr, Xtr, Xte):
    y = tr.y.to_numpy()
    out = {}
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0).fit(Xtr, np.log1p(y))
    out["HistGB (현행, log 오차)"] = np.expm1(m.predict(Xte)).clip(min=0)
    m = HistGradientBoostingRegressor(loss="poisson", max_iter=300, learning_rate=0.05, random_state=0).fit(Xtr, y)
    out["HistGB (Poisson 손실)"] = m.predict(Xte)
    m = e.fit_en(Xtr, np.log1p(y), tr.origin.to_numpy())
    out["Elastic Net (log)"] = np.expm1(m.predict(Xte)).clip(min=0)
    m = make_pipeline(StandardScaler(), PoissonRegressor(alpha=1e-3, max_iter=500)).fit(Xtr, y)
    out["Poisson GLM (중력모형형)"] = m.predict(Xte)
    return out


def part1_2(ctx):
    rows, band_rows, cal_rows = [], [], []
    for dist in e.TEST_DISTRICTS:
        tr, te, Xtr, Xte, path = setup(MONTH, dist, ctx)
        preds = fit_models(tr, Xtr, Xte)
        base = {"거리순": -te.dist_km.to_numpy(), "교통시간순": -te.transit_min.to_numpy(),
                "PATH-v0": np.array([path.at[a, e.SLOTS[s][1]] for a, s in zip(te.area_code, te.slot)])}
        scores = base | preds
        key = ["origin", "slot", "age_grp"]
        for (o, s, a), idx in te.groupby(key).indices.items():
            g = te.iloc[idx]
            if g.y.sum() <= 0:
                continue
            for name, sc in scores.items():
                rows.append({"구": dist, "model": name, "ndcg10": ndcg_recall(g.y.to_numpy(), sc[idx])[0]})
            if dist != "동대문구":
                continue
            for bname, lo, hi in BANDS:
                b = (g.transit_min.to_numpy() > lo) & (g.transit_min.to_numpy() <= hi)
                if b.sum() < K_BAND + 1 or g.y.to_numpy()[b].sum() <= 0:
                    continue
                for name, sc in scores.items():
                    band_rows.append({"band": bname, "model": name, "후보수": b.sum(),
                                      "ndcg5": ndcg_at(g.y.to_numpy()[b], sc[idx][b], K_BAND)})
        # 보정: 시험 구 전체를 상권별로 합쳐 예상 총량 vs 실제 (총량 맞춘 뒤)
        for name, p in preds.items():
            d = te.assign(p=p).groupby("area_code")[["y", "p"]].sum()
            d["p"] *= d.y.sum() / d.p.sum()
            big = d[d.y >= 20]
            lr = np.log((big.y + 5) / (big.p + 5))
            cal_rows.append({"구": dist, "model": name, "상권 총량 순위상관": stats.spearmanr(d.y, d.p).statistic,
                             "|log(실제/예상)| 중앙": lr.abs().median(), "2배 넘게 틀린 비율": (lr.abs() > np.log(2)).mean()})
        print("done", dist, flush=True)
    r = pd.DataFrame(rows)
    s = r.groupby(["model", "구"]).ndcg10.mean().unstack()
    s["평균"] = s.mean(axis=1)
    b = pd.DataFrame(band_rows).groupby(["model", "band"]).ndcg5.mean().unstack()[[x[0] for x in BANDS]]
    nb = pd.DataFrame(band_rows).groupby("band").후보수.median()
    c = pd.DataFrame(cal_rows).groupby("model")[["상권 총량 순위상관", "|log(실제/예상)| 중앙", "2배 넘게 틀린 비율"]].mean()
    for df, f in [(s, "model_compare_ndcg10.csv"), (b, "band_ndcg5_ddm.csv"), (c, "model_calibration.csv")]:
        df.round(3).to_csv(OUT / f, encoding="utf-8-sig")
    print("\n[2] 같은 구 홀드아웃 NDCG@10 (2026-06)\n", s.sort_values("평균", ascending=False).round(3).to_string())
    print("\n[2] 보정 (6개 구 평균, 실제 20명 이상 상권)\n", c.round(3).to_string())
    print("\n[1] 동대문구, 대중교통 단계 안에서 NDCG@5\n", b.sort_values("20~30분", ascending=False).round(3).to_string(),
          "\n단계별 후보 상권 수 중앙값:", nb.to_dict())


def part4(ctx):
    xw, alloc, origin_xy, area, static, path = ctx
    codes = static.index.to_numpy()
    names = area.set_index("area_code")[["area_name", "primary_district_name"]]
    months = ["202512", "202601", "202602", "202603", "202604", "202605", "202606", "202607"]
    panel = pd.concat([pd.read_csv(e.PANEL / f"seoul_od_E_{m}.csv.gz", dtype={"origin": str, "dest": str}) for m in months])
    panel = panel.groupby(["origin", "dest", "otype", "slot", "age20"], as_index=False)[["cnt", "masked"]].sum()
    camp = campus_dongs(xw)
    camp = camp[camp.stat_code.isin(origin_xy.index)]
    ddm = camp[camp.district == "동대문구"]
    lab = student_labels(panel, alloc, codes, camp.stat_code)
    te = e.long_table(lab, ddm.stat_code.tolist(), codes, origin_xy, area, alloc)
    seongbuk_areas = set(area.loc[area.primary_district_name == "성북구", "area_code"])
    near_sb = camp[camp.district.isin(["성북구"])].admin_name.tolist()
    res = {}
    for name, excl in [("전체 대학 학습(기존)", []), ("성북구 대학 빼고 학습", ["성북구"]),
                       ("성북·동대문 인접 3개 구 대학 빼고", ["성북구", "중랑구", "성동구"])]:
        tr_o = [o for o in camp.stat_code if o not in set(ddm.stat_code) and origin_xy.at[o, "district"] not in excl]
        tr = e.long_table(lab, tr_o, codes, origin_xy, area, alloc)
        pop = lab[lab.origin.isin(tr_o)].groupby("area_code")["y"].sum()
        Xtr, Xte = e.features(tr, static, path, pop, True), e.features(te, static, path, pop, True)
        keep = [c for c in Xtr.columns if Xtr[c].std() > 0]
        m = e.fit_en(Xtr[keep], np.log1p(tr.y.to_numpy()), tr.origin.to_numpy())
        t = te.assign(pred_n=np.expm1(m.predict(Xte[keep])).clip(min=0))
        t["act_share"] = t.y / t.groupby("origin").y.transform("sum")
        t["pred_share"] = t.pred_n / t.groupby("origin").pred_n.transform("sum")
        sb = t[t.area_code.isin(seongbuk_areas)]
        res[name] = {"학습 캠퍼스 동": len(tr_o),
                     "성북 실제/예상(합계)": sb.act_share.sum() / sb.pred_share.sum(),
                     **{f"{origin_xy.at[o, 'name']}": g.act_share.sum() / g.pred_share.sum() for o, g in sb.groupby("origin")}}
        t["ratio"] = np.log((t.act_share + 1e-4) / (t.pred_share + 1e-4))
        top = t[(t.pred_n >= 20) & (t.area_code.map(names.primary_district_name) != "동대문구")].nsmallest(12, "ratio")
        res[name]["덜 가는 상위 12 중 성북"] = int(top.area_code.isin(seongbuk_areas).sum())
        res[name]["덜 가는 상위 예"] = ", ".join(top.area_code.map(names.area_name).head(6))
    out = pd.DataFrame(res).T
    out.to_csv(OUT / "student_seongbuk_check.csv", encoding="utf-8-sig")
    print("\n[4] 대학생 성북 검증 (8달 합)\n성북구 캠퍼스 동:", near_sb, "\n", out.to_string())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    parts = sys.argv[1:] or ["1", "4"]
    ctx = None
    if {"1", "4"} & set(parts):
        ctx = e.load_common()
    if "1" in parts:
        part1_2(ctx)
    if "4" in parts:
        part4(ctx)


if __name__ == "__main__":
    main()
