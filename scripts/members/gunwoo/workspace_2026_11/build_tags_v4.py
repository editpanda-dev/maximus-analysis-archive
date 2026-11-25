# -*- coding: utf-8 -*-
"""태그 v4 (2026-11-18): v3 피처 + 건우·팀 라벨 합침 + 단체 회식 규칙 점수.

v3와 달라진 점
  1) Jev 원자 판단을 리뷰 점수가 있는 전 점포(11,335곳)로 늘렸다(분석/llm_judge/run_jev_all.py). v3는 4,804곳뿐이라
     나머지는 0.5로 채워져 애매 구간에 몰렸다.
  2) 학습 라벨에 팀 라벨(장한별·지우진 team1)을 더한다. 라벨러 한 명의 답 한 개가 한 행(분석/eval_tags_pooled.py).
     무작위 25곳 홀드아웃에서 v3 피처 + 합친 라벨이 가장 좋았다(느좋 0.989 · 감성 모임 0.921 · 가성비 혼밥 0.966).
  3) 단체 회식은 11-18에 정의를 좁혔다(감성 모임과 배타). 옛 정의 라벨로는 학습하지 않고 규칙 점수를 쓴다.
     점수 = '단체모임 하기 좋아요'·'매장이 넓어요'·'룸이 잘 되어있어요' 칩 비율과 log 면적의 전체 순위 평균.
     팀 라벨에서 둘 다 '예' 중앙값 0.65, 둘 다 '아니오' 최대 0.38(17문항 AUC 0.98).
     새 정의가 더 좁아 해당 = 점수 ≥ GROUP_HI(상위 10%) 이고 면적 ≥ GROUP_M2, 아님 = 점수 ≤ GROUP_LO(하위 70%), 그 사이 애매.
     5회차 라벨이 들어오면 이 기준선을 다시 잡는다.
  4) 감성 모임과 단체 회식이 둘 다 '해당'이면 감성 모임을 애매로 돌린다(둘은 배타, 사람이 고른다).

조합 태그를 v2 후보 안에서만 확률로 거르는 규칙, 업종 안 느좋, 제외·프랜차이즈 표시는 v3와 같다.
출력: 데이터/가공/store_level/store_tags_v4.csv
실행: ~/.venvs/maximus/bin/python 분석/build_tags_v4.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import ROOT, area_features, load, store_features  # noqa: E402
from build_tags_v3 import CAT_FLOOR, CAT_MIN_N, CAT_TOP, HI, LO, MIN_EACH, MIN_N  # noqa: E402
from eval_tags_pooled import C, features, labels  # noqa: E402

STORE = ROOT / "데이터/가공/store_level"
OUT = STORE / "store_tags_v4.csv"
GROUP = "단체 회식"
GROUP_CHIPS = ["단체모임 하기 좋아요", "매장이 넓어요", "룸이 잘 되어있어요"]
GROUP_HI, GROUP_LO, GROUP_M2 = 0.75, 0.6, 70


def group_score(d, meta, area):
    """단체 신호: 단체 칩 3개 비율과 log 면적의 전체 순위 평균(없는 값은 빼고 평균)."""
    share = pd.DataFrame({c: d.chips.map(lambda ch, c=c: c in ch).groupby(d.store_id).mean() for c in GROUP_CHIPS}).reindex(meta.index)
    sig = pd.concat([share.rank(pct=True), np.log(area.area_m2).rank(pct=True).rename("area")], axis=1)
    return sig.mean(axis=1, skipna=True)


def main():
    d = load()
    meta, *_ = store_features(d)
    area = area_features(meta)
    sets, has_jev = features()
    X = sets["v3"]
    print(f"가게 {len(X):,}곳 · Jev 있는 곳 {has_jev.mean():.1%}")
    v2 = pd.read_csv(STORE / "store_tags_v2.csv", keep_default_na=False).set_index("store_id").reindex(X.index)
    excluded = v2.excluded.astype(str) == "True"

    lab = labels()
    lab = lab[lab.store_id.isin(X.index) & (lab.tag != GROUP)]
    out = v2[["store_name", "category", "category_used", "flags", "franchise", "excluded", "rep_menu", "signature_menu"]].copy()
    cv_rows, tags_fit = [], []
    for t, g in lab.groupby("tag"):
        if min(g.y.sum(), (1 - g.y).sum()) < MIN_EACH or len(g) < MIN_N:
            continue
        # 가게 단위 5겹 교차검증(같은 가게의 여러 라벨러 답이 학습·시험에 갈리지 않게)
        p = pd.Series(np.nan, index=g.index)
        for tr, te in GroupKFold(5).split(g, groups=g.store_id):
            m = LogisticRegression(C=C, max_iter=5000).fit(X.loc[g.store_id.iloc[tr]], g.y.iloc[tr])
            p.iloc[te] = m.predict_proba(X.loc[g.store_id.iloc[te]])[:, 1]
        y = g.y.values.astype(bool)
        sure = ((p <= LO) | (p >= HI)).values
        cv_rows.append({"tag": t, "n": len(g), "auc": roc_auc_score(y, p), "acc": ((p >= 0.5).values == y).mean(),
                        "확정 비율": sure.mean(), "확정 정확도": ((p >= 0.5).values == y)[sure].mean()})
        m = LogisticRegression(C=C, max_iter=5000).fit(X.loc[g.store_id], g.y)
        out["p_" + t] = pd.Series(m.predict_proba(X)[:, 1], index=X.index).where(~excluded, 0.0).round(3)
        tags_fit.append(t)
    cvd = pd.DataFrame(cv_rows)
    print(cvd.round(3).to_string(index=False))
    print(f"가중 정확도 {np.average(cvd.acc, weights=cvd.n):.3f} · 확정 구간 정확도 "
          f"{np.average(cvd['확정 정확도'], weights=cvd.n * cvd['확정 비율']):.3f}")

    gs = group_score(d, meta, area).reindex(X.index)
    out["group_score"] = gs.where(~excluded, 0.0).round(3)
    a = area.area_m2.reindex(X.index)
    g_state = pd.Series("애매", index=X.index)
    g_state[(gs >= GROUP_HI) & (a >= GROUP_M2)] = "해당"
    g_state[gs <= GROUP_LO] = "아님"

    P = out[["p_" + t for t in tags_fit]]
    P.columns = tags_fit
    # 조합 태그는 v2 후보 안에서만 확률로 거르고, 느좋은 전체에 쓴다(v3와 같음, 라벨이 v2 후보 편향 표본이라서).
    v2tags = v2.tags.map(lambda x: set(x.split("|")) - {""})
    combo = [t for t in tags_fit if t != "느좋"]
    state = {}
    for s in out.index:
        st = {t: ("해당" if P.at[s, t] >= HI else "아님" if P.at[s, t] <= LO else "애매") for t in combo if t in v2tags[s]}
        if not excluded[s]:
            st[GROUP] = g_state[s]
        if st.get(GROUP) == "해당" and st.get("감성 모임") == "해당":
            st["감성 모임"] = "애매"  # 둘은 배타: 사람이 하나를 고른다
        state[s] = st
    out["tags"] = ["|".join([t for t in v2tags[s] if t not in combo and t != GROUP] + [t for t, v in state[s].items() if v == "해당"])
                   for s in out.index]
    out["dropped"] = ["|".join(t for t, v in state[s].items() if v == "아님") for s in out.index]
    out["느좋"] = P["느좋"] >= HI
    cat_n = P["느좋"].groupby(out.category_used).transform("size")
    cat_rk = P["느좋"].where(~excluded).groupby(out.category_used).rank(pct=True)
    out["느좋_업종내"] = ~out["느좋"] & ~excluded & (cat_n >= CAT_MIN_N) & (cat_rk >= CAT_TOP) & (P["느좋"] >= CAT_FLOOR)
    out["ambiguous"] = ["|".join((["느좋"] if LO < P.at[s, "느좋"] < HI else []) + [t for t, v in state[s].items() if v == "애매"])
                        for s in out.index]
    out["has_jev"] = has_jev.reindex(out.index)
    out.to_csv(OUT, encoding="utf-8-sig")
    print(f"전체 {len(out):,}곳: 느좋 {int(out['느좋'].sum()):,} · 태그 1개+ {(out.tags != '').sum():,} · 애매 태그 있는 곳 {(out.ambiguous != '').sum():,}")
    cnt = lambda col: out[col].str.split("|").explode().replace("", np.nan).dropna().value_counts()  # noqa: E731
    print(pd.DataFrame({"v2": v2.tags.str.split("|").explode().replace("", np.nan).dropna().value_counts(), "v4 해당": cnt("tags"),
                        "애매": cnt("ambiguous"), "뺌": cnt("dropped")}).fillna(0).astype(int).to_string())


if __name__ == "__main__":
    main()
