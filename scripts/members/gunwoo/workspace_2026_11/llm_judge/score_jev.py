"""A: 직접 질문 noul≥0.5 → yes. B: 원자 판단 확률 → 태그별 로지스틱 5겹 CV."""
import json, sys, collections, numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
R = [json.loads(l) for l in open(sys.argv[1])]; R = [r for r in R if r["response"]]
ok = collections.defaultdict(list)
for r in R:
    ans = r["response"]["answers"]
    for t, a in r["answers"].items():
        ok[t].append((ans["direct_" + t]["noul"] >= 0.5) == (a == "yes"))
allv = [x for v in ok.values() for x in v]
print(f"A 직접 질문: 정확도 {sum(allv)/len(allv):.2f} (질문 {len(allv)}, 실패 {len(open(sys.argv[1]).readlines())-len(R)})  " + " · ".join(f"{t} {sum(v)/len(v):.2f}({len(v)})" for t, v in sorted(ok.items(), key=lambda x: -len(x[1]))))
keys = sorted(k for k in R[0]["response"]["answers"] if k.startswith("atom_"))
X = np.array([[r["response"]["answers"][k]["noul"] for k in keys] for r in R])
tot = n = 0
for t in ok:
    idx = [i for i, r in enumerate(R) if t in r["answers"]]; y = np.array([R[i]["answers"][t] == "yes" for i in idx])
    if min(y.sum(), (~y).sum()) < 5: continue
    p = cross_val_predict(LogisticRegression(max_iter=2000), X[idx], y, cv=StratifiedKFold(5, shuffle=True, random_state=0))
    acc = (p == y).mean(); tot += acc * len(idx); n += len(idx); print(f"B 원자판단+로지스틱 {t}: {acc:.2f} ({len(idx)})")
print(f"B 가중 평균: {tot/n:.2f}")
