# -*- coding: utf-8 -*-
"""건우 라벨 + 팀 라벨(장한별·지우진 team1)을 합쳐 태그 모형을 다시 학습·평가한다.

라벨은 라벨러 한 명의 답 한 개가 한 행이다(라벨러끼리 갈린 문항은 자연히 0.5 근처로 학습된다).
평가 두 가지:
  1) 가게 단위 5겹 교차검증: 남겨 둔 가게는 다수결 답(동률은 뺌)으로 채점.
  2) 무작위 25곳 홀드아웃: 5회차 무작위 표본을 팀 두 명이 같은 답을 낸 문항만으로 채점. 학습에서 이 25곳은 뺀다.
     모델이 뽑지 않은 가게라 가장 정직한 시험이다.
피처 묶음:
  v3     = Jev 원자 판단 15 + 테마 전체 순위 12 + 프랜차이즈  (지금 v3과 같음)
  nojev  = 테마 전체 순위 12 + 테마 업종 내 순위 12 + 면적 순위 + 메뉴 중앙가 순위 + 메뉴 수 + 네이버 리뷰 수(log) + 프랜차이즈
  full   = nojev + Jev
Jev는 4,804곳에만 있어서 나머지 가게는 0.5로 채워진다. nojev가 v3만큼 나오면 전체 가게에 같은 품질로 쓸 수 있다.

실행: ~/.venvs/maximus/bin/python 분석/eval_tags_pooled.py
출력: 데이터/검토/store_level/pooled_eval.csv (태그·피처·학습 라벨별 AUC)
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import ROOT, area_features, load, store_features  # noqa: E402

STORE = ROOT / "데이터/가공/store_level"
REVIEW = ROOT / "데이터/검토/store_level"
GUNWOO = REVIEW / "labels_r1_r4"
TEAM = REVIEW / "team_labels_in/team1_labels_long.csv"
DB = ROOT / "수집/naver-review-crawler/crawler.db"
OUT = REVIEW / "pooled_eval.csv"
TAGS = ["느좋", "감성 모임", "데이트·기념일", "가성비 혼밥", "단체 회식"]
C = 0.5  # 로지스틱 규제(작을수록 강함). 라벨이 수백 개라 강하게 둔다


def labels():
    rows = []
    for f in GUNWOO.glob("semas*.json"):
        j = json.loads(f.read_text())
        rows += [("gunwoo", j["store_id"], t, a) for t, a in j.get("answers", {}).items()]
    g = pd.DataFrame(rows, columns=["labeler", "store_id", "tag", "answer"])
    t = pd.read_csv(TEAM)[["labeler", "store_id", "tag", "answer"]]
    lab = pd.concat([g, t])
    lab = lab[lab.answer.isin(["yes", "no"])].copy()
    lab["y"] = (lab.answer == "yes").astype(int)
    return lab


def menu_features(index):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    m = pd.read_sql("select store_id, price_won from place_menus", con)
    con.close()
    g = m.groupby("store_id")
    f = pd.DataFrame({"menu_n": g.size(), "price_med": g.price_won.median()}).reindex(index)
    return f


def features():
    d = load()
    meta, n, pct_cat, pct_all, _, _ = store_features(d)
    area = area_features(meta)
    jev = pd.read_csv(STORE / "jev_atomic_v1.csv").set_index("store_id").reindex(meta.index)
    v2 = pd.read_csv(STORE / "store_tags_v2.csv", keep_default_na=False).set_index("store_id").reindex(meta.index)
    menu = menu_features(meta.index)
    cat = meta.category_small
    base = pd.DataFrame(index=meta.index)
    base["franchise"] = (v2.franchise.astype(str) == "True").astype(float)
    base["area_pct"] = area.area_pct
    base["price_pct"] = menu.price_med.groupby(cat).rank(pct=True)  # 업종 안 가격 순위
    base["menu_n"] = np.log1p(menu.menu_n.fillna(0)) / np.log1p(50)
    base["reviews"] = np.log1p(pd.to_numeric(meta.naver_review_total, errors="coerce").fillna(0)) / 10
    nojev = pd.concat([pct_all.add_prefix("all_"), pct_cat.add_prefix("cat_"), base], axis=1).fillna(0.5)
    J = jev.add_prefix("jev_").fillna(0.5)
    sets = {"v3": pd.concat([J, pct_all.add_prefix("all_"), base[["franchise"]]], axis=1).fillna(0.5),
            "nojev": nojev, "full": pd.concat([J, nojev], axis=1)}
    has_jev = jev.notna().all(axis=1)
    return sets, has_jev


def fit_pred(X, tr, te):
    m = LogisticRegression(C=C, max_iter=5000)
    m.fit(X.loc[tr.store_id], tr.y)
    return m.predict_proba(X.loc[te])[:, 1]


def majority(g):
    s = g.groupby("store_id").y.mean()
    return s[s != 0.5].round().astype(int)


def auc(y, p):
    return roc_auc_score(y, p) if len(set(y)) > 1 else np.nan


def main():
    sets, has_jev = features()
    lab = labels()
    lab = lab[lab.store_id.isin(sets["v3"].index)]
    r5 = json.loads((GUNWOO / "candidates_r5.json").read_text())["stores"]
    rand25 = {s["store_id"] for s in r5 if s["kind"] == "random"}
    print(f"라벨 {len(lab)}행 (건우 {sum(lab.labeler == 'gunwoo')} · 팀 {sum(lab.labeler != 'gunwoo')}) · Jev 있는 라벨 가게 비율 "
          f"{has_jev.reindex(lab.store_id.unique()).mean():.2f}")
    rows = []
    for tag in TAGS:
        L = lab[lab.tag == tag]
        # 홀드아웃 정답: 무작위 25곳에서 팀 두 명이 같은 답
        T = L[L.store_id.isin(rand25) & (L.labeler != "gunwoo")].pivot_table(index="store_id", columns="labeler", values="y")
        T = T.dropna()
        T = T[T.hanbyeol == T.woojin].hanbyeol.astype(int)
        for train_on in ["gunwoo", "pooled"]:
            tr_all = L if train_on == "pooled" else L[L.labeler == "gunwoo"]
            if tr_all.y.nunique() < 2 or min(tr_all.y.sum(), (1 - tr_all.y).sum()) < 5:
                continue
            for fs, X in sets.items():
                # 1) 가게 단위 교차검증(학습 라벨 안에서, 다수결 채점)
                cv_p, cv_y = [], []
                stores = tr_all.store_id.unique()
                gkf = GroupKFold(5)
                for tri, tei in gkf.split(stores, groups=stores):
                    tr = tr_all[tr_all.store_id.isin(stores[tri])]
                    te = majority(tr_all[tr_all.store_id.isin(stores[tei])])
                    if tr.y.nunique() < 2 or te.empty:
                        continue
                    cv_p += list(fit_pred(X, tr, te.index))
                    cv_y += list(te.values)
                # 2) 무작위 25곳 홀드아웃
                tr = tr_all[~tr_all.store_id.isin(rand25)]
                ho = auc(T.values, fit_pred(X, tr, T.index)) if len(T) >= 5 and tr.y.nunique() > 1 else np.nan
                rows.append({"tag": tag, "train": train_on, "features": fs, "n_train": len(tr_all),
                             "cv_auc": auc(cv_y, cv_p), "holdout_n": len(T), "holdout_auc": ho})
    r = pd.DataFrame(rows)
    r.to_csv(OUT, index=False, encoding="utf-8-sig")
    show = r.pivot_table(index=["tag", "train"], columns="features", values=["cv_auc", "holdout_auc"]).round(3)
    print(show.to_string())
    w = r.groupby(["train", "features"]).apply(lambda g: pd.Series({
        "cv": np.average(g.cv_auc.fillna(0), weights=g.n_train * g.cv_auc.notna()),
        "holdout": np.average(g.holdout_auc.fillna(0), weights=g.holdout_n * g.holdout_auc.notna())}), include_groups=False)
    print("\n가중 평균\n" + w.round(3).to_string())


if __name__ == "__main__":
    main()
