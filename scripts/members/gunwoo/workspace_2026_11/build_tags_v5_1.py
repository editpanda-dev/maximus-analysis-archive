# -*- coding: utf-8 -*-
"""태그 v5.1 (2026-11-25): v5 결과에 단체 회식 확률 보정과 감성 모임 배타 처리를 더한다.

v5에서 바뀐 점
  1) 단체 회식 확률 p_단체 회식: 규칙 점수(group_score)를 새 정의 라벨(5회차 44곳)로 로지스틱 보정한 값.
     규칙 점수는 0~1이지만 확률이 아니라 감성 모임 확률과 비교할 수 없었다. 가게 하나씩 빼고 잰 AUC 0.81.
     방문 정보(회식·지인동료·가족 등)·Jev·업종을 더해도 0.79~0.82로 나아지지 않아(분석/eval_group_v1.py) 규칙 점수 하나만 쓴다.
     해당·아님 기준은 v5 그대로다(점수 ≥ 0.65 & 50㎡ / ≤ 0.4).
  2) 감성 모임과 단체 회식은 한 가게에 하나만 붙는다(교집합 0).
     v5는 둘 다 '해당'이면 감성 모임을 애매로 돌려 사람이 고르게 했다(747곳이 애매로 쌓임).
     v5.1은 확률이 높은 쪽 하나만 남기고, 다른 쪽은 해당·애매에서 빼서 dropped로 옮긴다.
     둘 다 애매인 가게도 확률이 높은 쪽만 애매로 남긴다.
출력: 데이터/가공/store_level/store_tags_v5_1.csv (열은 v5와 같고 p_단체 회식, exclusive_note 추가)
실행: ~/.venvs/maximus/bin/python 분석/build_tags_v5_1.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).parent))
from eval_tags_v5 import r5_labels  # noqa: E402

STORE = Path(__file__).resolve().parents[1] / "데이터/가공/store_level"
SRC, OUT = STORE / "store_tags_v5.csv", STORE / "store_tags_v5_1.csv"
G, M = "단체 회식", "감성 모임"


def split(s):
    return [t for t in s.split("|") if t]


def main():
    v = pd.read_csv(SRC, keep_default_na=False, index_col=0)
    gs = v.group_score.astype(float)
    lab = r5_labels()
    lab = lab[(lab.tag == G) & lab.store_id.isin(v.index)]
    cal = LogisticRegression(C=1e3).fit(gs.loc[lab.store_id].values.reshape(-1, 1), lab.y)
    v[f"p_{G}"] = cal.predict_proba(gs.values.reshape(-1, 1))[:, 1].round(3)
    pm = v[f"p_{M}"].replace("", np.nan).astype(float)
    pg = v[f"p_{G}"]

    tags, amb, drop = v.tags.map(split), v.ambiguous.map(split), v.dropped.map(split)
    note = pd.Series("", index=v.index)
    for s in v.index:
        has = {t: (t in tags[s]) or (t in amb[s]) for t in (G, M)}
        if not (has[G] and has[M]):
            continue
        # v5가 충돌로 애매로 돌린 감성 모임(확률 ≥ 0.7)은 해당 후보로 본다
        win, lose = (G, M) if pg[s] >= (pm[s] if not np.isnan(pm[s]) else 0) else (M, G)
        if win == M and M in amb[s] and pm[s] >= 0.7 and G in tags[s]:
            amb[s].remove(M)
            tags[s].append(M)
        for lst in (tags[s], amb[s]):
            if lose in lst:
                lst.remove(lose)
        if lose not in drop[s]:
            drop[s].append(lose)
        note[s] = f"{win} 남김 (단체 {pg[s]:.2f} vs 감성 {pm[s]:.2f})"
    v["tags"], v["ambiguous"], v["dropped"] = tags.map("|".join), amb.map("|".join), drop.map("|".join)
    v["exclusive_note"] = note
    v.to_csv(OUT, encoding="utf-8-sig")

    t = v.tags.map(split)
    both = t.map(lambda x: G in x and M in x).sum()
    print(f"보정: p = 1/(1+exp(-({cal.coef_[0][0]:.2f}·점수 {cal.intercept_[0]:+.2f})))")
    print(f"배타 처리 {int((note != '').sum())}곳 · 단체 남김 {int(note.str.startswith(G).sum())} · 감성 남김 {int(note.str.startswith(M).sum())}")
    print(f"단체 회식 해당 {t.map(lambda x: G in x).sum()} · 감성 모임 해당 {t.map(lambda x: M in x).sum()} · 둘 다 {both}")
    print(f"애매: 단체 {v.ambiguous.str.contains(G).sum()} · 감성 {v.ambiguous.str.contains(M).sum()}")


if __name__ == "__main__":
    main()
