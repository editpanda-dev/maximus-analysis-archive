# -*- coding: utf-8 -*-
"""단체 회식 개선 후보 비교 (2026-11-25).

문제: v5 단체 회식은 규칙 점수(단체 칩 3개 + 면적 순위 평균) ≥ 0.65 & 50㎡라서 24,370곳 중 4,567곳(19%)이 해당,
      11,151곳(46%)이 애매다. 라벨 표본이 단체 후보 위주라 기준선이 넓게 잡혔다.
후보
  rule     v5 규칙 점수 그대로
  rule+vi  규칙 점수 성분 + 방문 정보(회식·지인동료·가족·친목·혼자·예약 비율)
  full     rule+vi + Jev(group·spacious·alcohol) + 업종(고기 구이·회·중식·뷔페) 표시
평가: 새 정의(11-18) 라벨 = 5회차 단체 회식 답 44곳. 가게 하나씩 빼고 학습하는 LOO AUC.
      팀 라벨(옛 정의, 한별·우진 57문항)은 참고용으로만 같은 모형을 적용해 본다.
겹침: 5회차에서 감성 모임·단체 회식을 둘 다 '예'로 찍은 가게를 따로 본다.
출력: 데이터/검토/store_level/group_eval_v1.csv
실행: ~/.venvs/maximus/bin/python 분석/eval_group_v1.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import area_features, load, store_features  # noqa: E402
from build_tags_v4 import GROUP_CHIPS  # noqa: E402
from eval_tags_pooled import REVIEW, STORE, auc, labels  # noqa: E402
from eval_tags_v5 import r5_labels  # noqa: E402
from eval_visit_info_v0 import visit_features  # noqa: E402

OUT = REVIEW / "group_eval_v1.csv"
GROUP = "단체 회식"
GROUP_CATS = ["돼지고기 구이/찜", "소고기 구이/찜", "닭/오리고기 구이/찜", "해산물 구이/찜", "횟집", "일식 회/초밥", "중국집", "뷔페", "족발/보쌈"]
VISIT = ["dinner_team", "colleague", "family", "social", "solo", "reserved"]


def group_features():
    d = load()
    meta, *_ = store_features(d, min_n=10)
    area = area_features(meta)
    share = pd.DataFrame({c: d.chips.map(lambda ch, c=c: c in ch).groupby(d.store_id).mean() for c in GROUP_CHIPS}).reindex(meta.index)
    X = share.rank(pct=True).add_prefix("rk_")
    X["rk_area"] = np.log(area.area_m2).rank(pct=True)
    X["rule"] = X.mean(axis=1, skipna=True)
    X["area_m2"] = area.area_m2
    V = visit_features().reindex(meta.index)
    for c in VISIT:
        X["vi_" + c] = V[c]
    X["vi_n"] = np.log1p(V.n_visit.fillna(0))
    J = pd.read_csv(STORE / "jev_atomic_v1.csv").set_index("store_id").reindex(meta.index)
    for c in ["group", "spacious", "alcohol"]:
        X["jev_" + c] = J[c]
    X["cat_group"] = meta.category_small.isin(GROUP_CATS).astype(float)
    X["category"] = meta.category_small
    return X


SETS = {
    "rule": ["rule"],
    "rule+vi": [f"rk_{c}" for c in GROUP_CHIPS] + ["rk_area"] + [f"vi_{c}" for c in VISIT],
    "full": [f"rk_{c}" for c in GROUP_CHIPS] + ["rk_area"] + [f"vi_{c}" for c in VISIT]
            + ["jev_group", "jev_spacious", "jev_alcohol", "cat_group"],
}


def prep(X, cols):
    Z = X[cols].astype(float)
    return Z.fillna(Z.median())


def loo(X, cols, lab):
    Z = prep(X, cols)
    p = np.empty(len(lab))
    for i in range(len(lab)):
        tr = np.arange(len(lab)) != i
        m = LogisticRegression(C=0.5, max_iter=5000).fit(Z.loc[lab.store_id[tr]], lab.y[tr])
        p[i] = m.predict_proba(Z.loc[[lab.store_id.iloc[i]]])[0, 1]
    return p


def main():
    X = group_features()
    r5 = r5_labels()
    lab = r5[(r5.tag == GROUP) & r5.store_id.isin(X.index)].reset_index(drop=True)
    team = labels()
    team = team[(team.tag == GROUP) & team.labeler.isin(["hanbyeol", "woojin"]) & team.store_id.isin(X.index)]
    print(f"새 정의 라벨 {len(lab)}곳(예 {lab.y.sum()}) · 팀 옛 정의 {len(team)}문항(예 {team.y.sum()})")

    rows = []
    for nm, cols in SETS.items():
        p = lab.rule.values if False else (X.loc[lab.store_id, "rule"].values if nm == "rule" else loo(X, cols, lab))
        full = LogisticRegression(C=0.5, max_iter=5000).fit(prep(X, cols).loc[lab.store_id], lab.y) if nm != "rule" else None
        pt = X.loc[team.store_id, "rule"].values if nm == "rule" else full.predict_proba(prep(X, cols).loc[team.store_id])[:, 1]
        rows.append(dict(features=nm, auc_r5_loo=auc(lab.y.values, p), auc_team_oldef=auc(team.y.values, pt)))
        if full is not None:
            print(nm, dict(zip(cols, full.coef_[0].round(2))))
    r = pd.DataFrame(rows)

    # 업종 하나만으로 얼마나 맞히나, 해당 업종 비율
    lab = lab.assign(cat=X.loc[lab.store_id, "category"].values, area=X.loc[lab.store_id, "area_m2"].values,
                     dinner=X.loc[lab.store_id, "vi_dinner_team"].values, colleague=X.loc[lab.store_id, "vi_colleague"].values,
                     cat_group=X.loc[lab.store_id, "cat_group"].values)
    print("\n업종 표시 AUC", round(auc(lab.y.values, lab.cat_group.values), 3))
    print(lab.groupby("y")[["area", "dinner", "colleague", "cat_group"]].median())

    # 감성 모임과 겹친 가게
    both = r5[r5.tag.isin([GROUP, "감성 모임"])].pivot_table(index="store_id", columns="tag", values="y")
    both = both.join(X[["rule", "area_m2", "vi_dinner_team", "vi_colleague", "vi_social", "vi_family", "category"]], how="left")
    both["kind"] = np.select([(both[GROUP] == 1) & (both["감성 모임"] == 1), both[GROUP] == 1, both["감성 모임"] == 1],
                             ["둘 다", "단체만", "감성만"], "둘 다 아님")
    print("\n5회차 감성 모임 × 단체 회식\n" + both.groupby("kind")[["rule", "area_m2", "vi_dinner_team", "vi_colleague", "vi_social", "vi_family"]]
          .median().round(3).assign(n=both.kind.value_counts()).to_string())
    print(both[both.kind == "둘 다"].category.value_counts().to_string())

    r.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("\n" + r.round(3).to_string())


if __name__ == "__main__":
    main()
