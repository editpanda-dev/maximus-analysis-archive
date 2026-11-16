# -*- coding: utf-8 -*-
"""태그 v3: Jev 원자 판단 15개 + 테마 점수 12개 → 태그별 로지스틱. 확실한 것만 확정하고 애매한 것은 사람이 본다.

판단은 Jev(분석/llm_judge/run_jev_all.py), 결정은 여기 코드. 라벨 442문항 5겹 교차검증 0.80(테마만 0.79, 차이는 유의하지 않음).
확률 ≥ HI → 해당, ≤ LO → 해당 아님, 그 사이 → 애매(사람 확인). 라벨에서 확정 구간 정확도 0.87, 전체의 68%.
라벨이 없거나 한쪽뿐인 태그(단체 회식·야장·야외석·이색 체험)와 제외·프랜차이즈 표시는 v2 값을 그대로 쓴다.

5회차 = 애매 구간 + 무작위 표본(모델이 안 뽑은 곳을 얼마나 놓치는지) + 다시 찍기(라벨 일관성). 셋 다 모델 판정을 가리고 묻는다.
출력: 데이터/가공/store_level/store_tags_v3.csv, <5회차 후보.json>
실행: ~/.venvs/maximus/bin/python 분석/build_tags_v3.py <라벨 폴더> <5회차 후보.json> [이전 후보.json ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import ROOT, SEED, area_features, evidence, load, store_features  # noqa: E402

STORE = ROOT / "데이터/가공/store_level"
OUT = STORE / "store_tags_v3.csv"
LO, HI = 0.3, 0.7
CAT_TOP, CAT_FLOOR, CAT_MIN_N = 0.95, 0.4, 20  # 업종 안 느좋: 업종 내 순위, 최소 확률, 업종 최소 가게 수
ROUND = 5
N_AMBIG, N_RANDOM, N_RETEST = 45, 25, 15
RANDOM_ASK = ["느좋", "감성 모임", "데이트·기념일", "가성비 혼밥", "단체 회식"]
MIN_EACH = 5  # 예·아니오가 각각 이만큼은 있어야 학습
MIN_N = 20  # 라벨이 이보다 적은 태그(4회차의 이색 체험 17개 등)는 학습하지 않고 v2 규칙을 쓴다


def read_answers(label_dir):
    rows = []
    for f in Path(label_dir).glob("*.json"):
        j = json.loads(f.read_text())
        if "store_id" not in j:
            continue
        rows += [(j["store_id"], t, a == "yes") for t, a in j.get("answers", {}).items() if a in ("yes", "no")]
    return pd.DataFrame(rows, columns=["store_id", "tag", "y"])


def main(label_dir: Path, out_json: Path, prev: list[Path]):
    rng = np.random.default_rng(SEED + ROUND)
    d = load()
    meta, n, pct, pct_all, hit, evid = store_features(d)
    area = area_features(meta)
    jev = pd.read_csv(STORE / "jev_atomic_v1.csv").set_index("store_id").reindex(meta.index)
    v2 = pd.read_csv(STORE / "store_tags_v2.csv", keep_default_na=False).set_index("store_id").reindex(meta.index)
    excluded, franchise = v2.excluded.astype(str) == "True", v2.franchise.astype(str) == "True"
    X = pd.concat([jev.add_prefix("jev_"), pct_all], axis=1)
    X["franchise"] = franchise.astype(float)
    X = X.fillna(0.5)

    lab = read_answers(label_dir)
    lab = lab[lab.store_id.isin(X.index)]
    out = v2[["store_name", "category", "category_used", "flags", "franchise", "excluded", "rep_menu", "signature_menu"]].copy()
    cv_rows, tags_fit = [], []
    for t, g in lab.groupby("tag"):
        y = g.y.values
        if min(y.sum(), (~y).sum()) < MIN_EACH or len(y) < MIN_N:
            continue
        m = LogisticRegression(max_iter=3000)
        p = cross_val_predict(m, X.loc[g.store_id], y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
        sure = (p <= LO) | (p >= HI)
        cv_rows.append({"tag": t, "n": len(y), "acc": ((p >= 0.5) == y).mean(), "확정 비율": sure.mean(),
                        "확정 정확도": ((p >= 0.5) == y)[sure].mean()})
        prob = pd.Series(m.fit(X.loc[g.store_id], y).predict_proba(X)[:, 1], index=X.index)
        out["p_" + t] = prob.where(~excluded, 0.0).round(3)
        tags_fit.append(t)
    cvd = pd.DataFrame(cv_rows)
    print(cvd.round(2).to_string(index=False))
    print(f"가중 정확도 {np.average(cvd.acc, weights=cvd.n):.2f} · 확정 구간 정확도 {np.average(cvd['확정 정확도'], weights=cvd.n * cvd['확정 비율']):.2f}")

    P = out[["p_" + t for t in tags_fit]]
    P.columns = tags_fit
    # 조합 태그 라벨은 v2가 후보로 뽑은 가게에서만 받았다(예 비율 60~80%). 그 밖의 가게에 확률을 그대로 쓰면
    # 가성비 감성이 전체의 54%에 붙는다. 그래서 조합 태그는 v2 후보 안에서만 확률로 거르고, 느좋만 전체에 쓴다.
    v2tags = v2.tags.map(lambda x: set(x.split("|")) - {""})
    combo = [t for t in tags_fit if t != "느좋"]
    state = {s: {t: ("해당" if P.at[s, t] >= HI else "아님" if P.at[s, t] <= LO else "애매") for t in combo if t in v2tags[s]}
             for s in out.index}
    out["tags"] = ["|".join([t for t in v2tags[s] if t not in combo] + [t for t, v in state[s].items() if v == "해당"]) for s in out.index]
    out["dropped"] = ["|".join(t for t, v in state[s].items() if v == "아님") for s in out.index]
    out["느좋"] = P["느좋"] >= HI
    # 업종 안 느좋(2026-11-16 건우 제안): 국밥·족발처럼 업종 전체가 낮은 곳도 그 업종 상위 5%이고 확률 0.4 이상이면 따로 표시.
    # 전체 느좋과 섞지 않는 별도 배지다. 아직 라벨로 확인하지 않았다.
    cat_n = P["느좋"].groupby(out.category_used).transform("size")
    cat_rk = P["느좋"].where(~excluded).groupby(out.category_used).rank(pct=True)
    out["느좋_업종내"] = ~out["느좋"] & ~excluded & (cat_n >= CAT_MIN_N) & (cat_rk >= CAT_TOP) & (P["느좋"] >= CAT_FLOOR)
    out["ambiguous"] = ["|".join((["느좋"] if LO < P.at[s, "느좋"] < HI else []) + [t for t, v in state[s].items() if v == "애매"])
                        for s in out.index]
    out.to_csv(OUT, encoding="utf-8-sig")
    print(f"전체 {len(out):,}곳: 느좋 {int(out['느좋'].sum()):,} · 태그 1개+ {(out.tags != '').sum():,} · 애매 태그 있는 곳 {(out.ambiguous != '').sum():,}")
    cnt = lambda col: out[col].str.split("|").explode().replace("", np.nan).dropna().value_counts()  # noqa: E731
    print(pd.DataFrame({"v2": v2.tags.str.split("|").explode().replace("", np.nan).dropna().value_counts(), "v3 해당": cnt("tags"),
                        "애매": cnt("ambiguous"), "뺌": cnt("dropped")}).fillna(0).astype(int).to_string())

    # 5회차
    prev_stores = {s["id"]: s for p in prev for s in json.loads(p.read_text())["stores"]}
    pool = out[~out.index.isin(prev_stores) & ~excluded]
    amb = pool[pool.ambiguous != ""]
    w = amb.ambiguous.str.count(r"\|") + 1  # 애매한 태그가 많은 가게를 더 자주
    pick_amb = list(rng.choice(amb.index, size=min(N_AMBIG, len(amb)), replace=False, p=(w / w.sum()).values))
    rest = pool.index.difference(pick_amb)
    pick_rand = list(rng.choice(rest, size=N_RANDOM, replace=False))
    old = lab[lab.store_id.isin(prev_stores)].groupby("store_id").tag.agg(list)
    pick_re = list(rng.choice(old.index, size=min(N_RETEST, len(old)), replace=False))
    n_by = pd.Series(n, index=meta.index)
    stores = []
    for kind, sid in rng.permutation([("ambiguous", s) for s in pick_amb] + [("random", s) for s in pick_rand] + [("retest", s) for s in pick_re]):
        r = out.loc[sid]
        ask = {"ambiguous": r.ambiguous.split("|"), "random": RANDOM_ASK, "retest": old.get(sid, [])}[kind]
        chips, snippets = evidence(d, meta, sid, n_by[sid], pct)
        a = area.area_m2.get(sid)
        stores.append({
            # 다시 찍기는 예전 답을 덮어쓰지 않고 가려지도록 문서 id를 따로 둔다
            "id": ("r5retest:" + sid) if kind == "retest" else sid, "store_id": sid, "kind": kind,
            "name": r.store_name, "naver_name": meta.at[sid, "naver_place_name"], "area": meta.at[sid, "area_name"],
            "category": r.category, "naver_reviews": int(float(meta.at[sid, "naver_review_total"] or 0)),
            "collected": int(n_by[sid]), "place_url": f"https://m.place.naver.com/restaurant/{meta.at[sid, 'place_id']}/home",
            "area_m2": None if pd.isna(a) else round(float(a)),
            "lic_uptae": None if pd.isna(area.lic_uptae.get(sid)) else area.lic_uptae.get(sid),
            "rep_menu": r.rep_menu, "signature_menu": r.signature_menu, "flags": r["flags"],
            "chips": chips, "snippets": snippets, "ask": ask,
            "claims": [{"tag": t, "claim": None} for t in ask],  # 모델 판정은 가린다
            "model": {t: float(P.at[sid, t]) for t in ask if t in P.columns},
        })
    desc = {t["name"]: t["desc"] for p in prev for t in json.loads(p.read_text())["tags"]}
    out_json.write_text(json.dumps({"round": ROUND, "mode": "confirm", "tags": [{"name": k, "desc": v} for k, v in desc.items()],
                                    "stores": stores}, ensure_ascii=False, indent=1))
    print(f"{ROUND}회차 {len(stores)}곳(애매 {len(pick_amb)} · 무작위 {len(pick_rand)} · 다시 찍기 {len(pick_re)}), "
          f"질문 {sum(len(s['ask']) for s in stores)}개 → {out_json}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])
