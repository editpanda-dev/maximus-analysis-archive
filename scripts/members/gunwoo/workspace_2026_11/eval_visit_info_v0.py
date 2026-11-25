# -*- coding: utf-8 -*-
"""방문 정보(동행·목적·예약·대기·방문 시각) 피처 1차 평가 (2026-11-25).

네이버 리뷰의 방문 정보 칩(visitCategories)을 가게별 비율로 바꿔 태그 모형에 넣으면 나아지는지 본다.
칩 코드와 한글 이름이 어긋난 행이 있어(예: v_significant_other:아이) 화면에 보이는 한글 이름만 쓴다.
피처
  visit   동행(혼자·연인·친구·지인동료·가족) · 목적(데이트·친목·일상·회식·기념일·비즈니스·나들이) ·
          예약 후 이용 · 포장·배달 · 바로 입장 · 저녁 9시 이후 방문 비율, 방문 정보 달린 리뷰 수(log)
  v3      Jev 원자 판단 15 + 테마 순위 12 + 프랜차이즈 (v4·v5와 같음)
평가 (방문 정보가 5건 이상인 라벨 가게만)
  A  5회차 시험셋 (학습: 1~4회차 + 팀) — eval_tags_v5.py와 같은 분할
  B  모든 라벨 가게 5겹 교차검증(가게 단위) + 부트스트랩 1,000번으로 AUC 차이의 95% 구간
출력: 데이터/검토/store_level/visit_info_eval_v0.csv
실행: ~/.venvs/maximus/bin/python 분석/eval_visit_info_v0.py
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).parent))
from eval_tags_pooled import C, DB, REVIEW, auc, features, labels  # noqa: E402
from eval_tags_v5 import R5_CAND, TAGS, r5_labels  # noqa: E402

OUT = REVIEW / "visit_info_eval_v0.csv"
MIN_VISIT = 5
GROUPS = {
    "solo": ["혼자"], "couple": ["연인・배우자"], "friend": ["친구"], "colleague": ["지인・동료"],
    "family": ["부모님", "아이", "친척・형제자매", "가족모임"],
    "date": ["데이트"], "social": ["친목"], "daily": ["일상"], "dinner_team": ["회식"],
    "anniv": ["기념일"], "business": ["비즈니스"], "outing": ["나들이", "여행"],
    "reserved": ["예약 후 이용"], "pickup": ["포장·배달 이용"], "no_wait": ["바로 입장"],
}


def visit_features():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    d = pd.read_sql("select store_id, visit_categories, visit_datetime from review_visit_info", con)
    con.close()
    d = d[d.visit_categories.fillna("") != ""]
    names = d.visit_categories.str.split("|").apply(lambda xs: {x.split(":", 1)[-1].strip() for x in xs})
    f = pd.DataFrame({"store_id": d.store_id})
    for k, vs in GROUPS.items():
        f[k] = names.apply(lambda s, vs=vs: float(bool(s & set(vs))))
    hour = (pd.to_datetime(d.visit_datetime, errors="coerce", utc=True).dt.tz_convert("Asia/Seoul").dt.hour)
    f["late"] = (hour >= 21).astype(float).where(hour.notna())
    g = f.groupby("store_id")
    out = g.mean()
    out["n_visit"] = g.size()
    return out


def fit(X, tr_ids, tr_y, te_ids):
    m = LogisticRegression(C=C, max_iter=5000)
    m.fit(X.loc[tr_ids], tr_y)
    return m.predict_proba(X.loc[te_ids])[:, 1]


def main():
    sets, _ = features()
    X3 = sets["v3"]
    V = visit_features()
    ok = V.index[V.n_visit >= MIN_VISIT].intersection(X3.index)
    Vf = V.reindex(X3.index)
    Vf["n_visit"] = np.log1p(Vf.n_visit.fillna(0)) / np.log1p(100)
    Vf = Vf.fillna(Vf.loc[ok].mean())
    sets_ = {"v3": X3, "visit": Vf, "v3+visit": pd.concat([X3, Vf.add_prefix("vi_")], axis=1)}

    lab_all = pd.concat([labels(), r5_labels()], ignore_index=True)
    lab_all = lab_all[lab_all.store_id.isin(X3.index)]
    print(f"방문 정보 {MIN_VISIT}건+ 가게 {len(ok):,} / 태그 피처 가게 {len(X3):,}")
    print(f"라벨 가게 {lab_all.store_id.nunique()} 중 방문 정보 있는 곳 {lab_all[lab_all.store_id.isin(ok)].store_id.nunique()}")

    cand = json.loads(R5_CAND.read_text())["stores"]
    r5ids = {s["store_id"] for s in cand if not s["id"].startswith("r5retest")}
    rows, rng = [], np.random.default_rng(0)
    for tag in TAGS:
        L = lab_all[(lab_all.tag == tag) & lab_all.store_id.isin(ok)]
        # A: 5회차 시험셋
        tr, te = L[~L.store_id.isin(r5ids) & (L.labeler != "gunwoo_r5")], L[L.labeler == "gunwoo_r5"]
        if tr.y.nunique() > 1 and te.y.nunique() > 1:
            for nm, X in sets_.items():
                p = fit(X, tr.store_id, tr.y, list(te.store_id))
                rows.append(dict(tag=tag, eval="A_r5_test", features=nm, n=len(te), yes=int(te.y.sum()), auc=auc(te.y.values, p)))
        # B: 가게 단위 5겹 CV
        stores = L.store_id.unique()
        oof = {nm: np.full(len(L), np.nan) for nm in sets_}
        for a, b in GroupKFold(5).split(stores, groups=stores):
            trm, tem = L.store_id.isin(stores[a]).values, L.store_id.isin(stores[b]).values
            if L.y.values[trm].std() == 0:
                continue
            for nm, X in sets_.items():
                oof[nm][tem] = fit(X, L.store_id.values[trm], L.y.values[trm], list(L.store_id.values[tem]))
        y = L.y.values
        for nm in sets_:
            rows.append(dict(tag=tag, eval="B_cv", features=nm, n=len(L), yes=int(y.sum()), auc=auc(y, oof[nm])))
        diffs = []
        for _ in range(1000):
            i = rng.integers(0, len(y), len(y))
            if len(set(y[i])) > 1:
                diffs.append(auc(y[i], oof["v3+visit"][i]) - auc(y[i], oof["v3"][i]))
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        rows.append(dict(tag=tag, eval="B_cv_diff(v3+visit − v3)", features="95%CI", n=len(L), yes=int(y.sum()),
                         auc=float(np.mean(diffs)), ci_lo=lo, ci_hi=hi))
    r = pd.DataFrame(rows)
    r.to_csv(OUT, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(r.round(3).to_string())
    # 방문 비율이 태그와 어떻게 같이 움직이나 (라벨 가게, 예=1 평균 − 아니오=0 평균)
    L = lab_all[lab_all.store_id.isin(ok)].merge(V, left_on="store_id", right_index=True)
    eff = L.groupby(["tag", "y"])[list(GROUPS) + ["late"]].mean().round(3)
    print("\n태그 예/아니오별 방문 비율 평균\n" + eff.loc[TAGS].to_string())


if __name__ == "__main__":
    main()
