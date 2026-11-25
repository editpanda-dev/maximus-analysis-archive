# -*- coding: utf-8 -*-
"""칩 리뷰가 적은 가게의 느좋·데이트·감성 모임·가성비 혼밥 확률 v0 (2026-11-24).

v5는 칩 비율 순위가 피처라 칩 리뷰 10건 미만 가게에는 못 쓴다. 이 가게들은 리뷰 본문만으로 받은 Jev 원자 판단 15개
(분석/llm_judge/run_jev_textonly.py)에 'Jev만 쓰는 로지스틱'을 적용한다.
학습: v5와 같은 라벨(건우 1~5회차 + 팀). 학습 가게의 Jev는 칩 줄이 들어간 판(jev_atomic_v1)이라 적용 대상과 입력이 조금 다르다.
평가: 가게 단위 5겹 교차검증 AUC(다수결 채점), 같은 라벨에서 v3 피처(Jev + 칩 순위) 모형과 비교.
출력: 데이터/가공/store_level/store_vibe_textonly_v0.csv
실행: ~/.venvs/maximus/bin/python 분석/build_vibe_textonly_v0.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).parent))
from build_tags_v5 import labels_with_r5  # noqa: E402
from eval_tags_pooled import C, features, majority  # noqa: E402

STORE = Path(__file__).resolve().parents[1] / "데이터/가공/store_level"
OUT = STORE / "store_vibe_textonly_v0.csv"
TAGS = ["느좋", "데이트·기념일", "감성 모임", "가성비 혼밥"]


def cv_auc(X, L):
    stores = L.store_id.unique()
    ps, ys = [], []
    for a, b in GroupKFold(5).split(stores, groups=stores):
        tr = L[L.store_id.isin(stores[a])]
        te = majority(L[L.store_id.isin(stores[b])])
        if tr.y.nunique() < 2 or te.empty:
            continue
        m = LogisticRegression(C=C, max_iter=5000).fit(X.loc[tr.store_id], tr.y)
        ps += list(m.predict_proba(X.loc[te.index])[:, 1]); ys += list(te.values)
    return roc_auc_score(ys, ps)


def main():
    sets, _ = features()
    J = pd.read_csv(STORE / "jev_atomic_v1.csv").set_index("store_id")
    T = pd.read_csv(STORE / "jev_atomic_textonly_v1.csv").set_index("store_id")[J.columns]
    lab = labels_with_r5()
    lab = lab[lab.store_id.isin(J.index) & lab.store_id.isin(sets["v3"].index)]
    out = pd.DataFrame(index=T.index)
    for t in TAGS:
        L = lab[lab.tag == t]
        a_j, a_v3 = cv_auc(J, L), cv_auc(sets["v3"], L)
        m = LogisticRegression(C=C, max_iter=5000).fit(J.loc[L.store_id], L.y)
        out["p_" + t] = m.predict_proba(T)[:, 1].round(3)
        print(f"{t}: 라벨 {len(L)}행 · CV AUC Jev만 {a_j:.3f} / v3(Jev+칩) {a_v3:.3f}")
    meta = pd.read_csv(Path(__file__).resolve().parents[1] / "데이터/가공/naver_reviews/dining_store_by_area.csv") \
        .drop_duplicates("store_id").set_index("store_id")
    out = meta[["store_name", "naver_place_name", "subcategory", "naver_review_total"]].join(out, how="right")
    out.to_csv(OUT, encoding="utf-8-sig")
    print(f"{len(out)}곳 → {OUT}")
    print("느좋 확률 0.6 이상", int((out.p_느좋 >= 0.6).sum()), "곳 / 0.8 이상", int((out.p_느좋 >= 0.8).sum()), "곳")


if __name__ == "__main__":
    main()
