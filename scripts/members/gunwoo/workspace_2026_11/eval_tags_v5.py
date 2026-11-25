# -*- coding: utf-8 -*-
"""태그 v5 후보 비교 (2026-11-23): 5회차 라벨을 시험셋으로, 새 피처가 v3 피처보다 나은지 본다.

시험셋: 5회차(애매 45 · 무작위 25 · 단체 경계 20) 건우 답. 이 가게들은 누구의 라벨이든 학습에서 뺀다.
  애매 = v4가 0.3~0.7로 본 가게라 가장 어려운 문항. 무작위 = 모델이 고르지 않은 가게.
학습: 건우 1~4회차 + 팀(한별·우진) 라벨, 라벨러 답 한 개가 한 행. 단체 회식은 정의가 바뀌어 여기서 비교하지 않는다.
피처 묶음
  v3      Jev 원자 판단 15 + 테마 전체 순위 12 + 프랜차이즈 (지금 v4와 같음)
  behav   v3 + 재방문 리뷰 비율·주말 방문 비율·리뷰 수(log)·업종 안 가격 순위·면적 순위·메뉴 수
  text    리뷰 본문 글자 n-gram TF-IDF 로지스틱만
  stack   v3 + text 확률(학습셋 안에서 5겹으로 만든 값)
  all     behav + text 확률
출력: 데이터/검토/store_level/v5_eval.csv
실행: ~/.venvs/maximus/bin/python 분석/eval_tags_v5.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).parent))
from eval_tags_pooled import C, REVIEW, features, labels  # noqa: E402
from build_keyword_theme_map_v0 import SRC  # noqa: E402

R5_DIR = REVIEW / "labels_r5/labels"
R5_CAND = REVIEW / "label_pages/main/candidates_r5.json"
OUT = REVIEW / "v5_eval.csv"
TAGS = ["느좋", "감성 모임", "데이트·기념일", "가성비 혼밥"]
TEXT_C = 2.0


def r5_labels():
    rows = []
    for f in R5_DIR.glob("semas*.json"):  # r5retest:* (다시 찍기)는 시험셋에서 뺀다
        j = json.loads(f.read_text())
        rows += [("gunwoo_r5", j["store_id"], t, a) for t, a in j.get("answers", {}).items()]
    lab = pd.DataFrame(rows, columns=["labeler", "store_id", "tag", "answer"])
    lab = lab[lab.answer.isin(["yes", "no"])].copy()
    lab["y"] = (lab.answer == "yes").astype(int)
    return lab


def behav_features(index):
    d = pd.read_csv(SRC, dtype=str, keep_default_na=False, encoding="utf-8-sig",
                    usecols=["store_id", "visit_count", "visit_date", "review_text"])
    d = d[d.store_id.isin(index)]
    v = pd.to_numeric(d.visit_count, errors="coerce")
    dt = pd.to_datetime(d.visit_date, errors="coerce")
    g = pd.DataFrame({"store_id": d.store_id, "revisit": (v >= 2).astype(float).where(v.notna()),
                      "weekend": (dt.dt.dayofweek >= 5).astype(float).where(dt.notna())}).groupby("store_id").mean()
    docs = d[d.review_text != ""].groupby("store_id").review_text.apply(" ".join).reindex(index).fillna("")
    return g.reindex(index), docs


def text_matrix(docs):
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=5, max_features=60000, sublinear_tf=True)
    return pd.Series(range(len(docs)), index=docs.index), vec.fit_transform(docs.values)


def text_fit_pred(M, pos, tr, te_ids):
    m = LogisticRegression(C=TEXT_C, max_iter=5000)
    m.fit(M[pos[tr.store_id].values], tr.y)
    return m.predict_proba(M[pos[list(te_ids)].values])[:, 1]


def text_oof(M, pos, tr, all_ids):
    """학습 라벨 가게는 5겹 밖 예측, 나머지 가게는 학습 전체로 예측한 텍스트 확률."""
    out = pd.Series(text_fit_pred(M, pos, tr, all_ids), index=all_ids)
    stores = tr.store_id.unique()
    for a, b in GroupKFold(5).split(stores, groups=stores):
        inner = tr[tr.store_id.isin(stores[a])]
        if inner.y.nunique() > 1:
            out[stores[b]] = text_fit_pred(M, pos, inner, stores[b])
    return out


def lr_pred(X, tr, te_ids):
    m = LogisticRegression(C=C, max_iter=5000)
    m.fit(X.loc[tr.store_id], tr.y)
    return m.predict_proba(X.loc[list(te_ids)])[:, 1]


def auc(y, p):
    return roc_auc_score(y, p) if len(set(y)) > 1 else np.nan


def main():
    sets, _ = features()
    X3 = sets["v3"]
    beh, docs = behav_features(X3.index)
    nojev = sets["nojev"]
    XB = pd.concat([X3, beh.fillna(beh.mean()), nojev[["reviews", "price_pct", "area_pct", "menu_n"]]], axis=1).fillna(0.5)
    pos, M = text_matrix(docs)

    train = labels()
    test = r5_labels()
    cand = json.loads(R5_CAND.read_text())["stores"]
    kind = {s["store_id"]: s["kind"] for s in cand if not s["id"].startswith("r5retest")}
    train = train[train.store_id.isin(X3.index) & ~train.store_id.isin(kind)]
    test = test[test.store_id.isin(X3.index)]
    print(f"학습 {len(train)}행 · 가게 {train.store_id.nunique()} / 시험 {len(test)}행 · 가게 {test.store_id.nunique()}")

    rows = []
    for tag in TAGS:
        tr, te = train[train.tag == tag], test[test.tag == tag]
        if te.y.nunique() < 2 or tr.y.nunique() < 2:
            continue
        ids = list(te.store_id)
        tprob = text_oof(M, pos, tr, X3.index)
        preds = {
            "v3": lr_pred(X3, tr, ids),
            "behav": lr_pred(XB, tr, ids),
            "text": text_fit_pred(M, pos, tr, ids),
            "stack": lr_pred(X3.assign(text=tprob), tr, ids),
            "all": lr_pred(XB.assign(text=tprob), tr, ids),
        }
        for fs, p in preds.items():
            for sub in ["전체", "ambiguous", "random"]:
                m = np.ones(len(te), bool) if sub == "전체" else te.store_id.map(kind).eq(sub).values
                rows.append({"tag": tag, "features": fs, "subset": sub, "n": int(m.sum()),
                             "yes": int(te.y.values[m].sum()), "auc": auc(te.y.values[m], p[m]),
                             "acc": ((p[m] >= 0.5) == te.y.values[m]).mean() if m.any() else np.nan})
    r = pd.DataFrame(rows)
    r.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(r.pivot_table(index=["tag", "subset", "n"], columns="features", values="auc").round(3).to_string())
    w = r[r.subset == "전체"].groupby("features").apply(lambda g: np.average(g.auc, weights=g.n), include_groups=False)
    print("\n시험셋 가중 AUC\n" + w.round(3).to_string())


if __name__ == "__main__":
    main()
