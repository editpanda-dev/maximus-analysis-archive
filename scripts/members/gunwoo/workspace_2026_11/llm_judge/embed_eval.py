"""임베딩(bge-m3) + 로지스틱. 태그별 5겹 교차검증 정확도. 리뷰 텍스트만 / 테마 점수만 / 둘 다."""
import json, sys, urllib.request
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
sys.path.insert(0, "분석")
from build_label_round import load, store_features
E = json.load(open(sys.argv[1])); rows = E["rows"]
def emb(texts):
    out = []
    for i in range(0, len(texts), 16):
        req = urllib.request.Request("http://localhost:11434/api/embed", json.dumps({"model": "bge-m3", "input": texts[i:i+16]}).encode(), {"Content-Type": "application/json"})
        out += json.load(urllib.request.urlopen(req, timeout=600))["embeddings"]
    return np.array(out)
X = emb([r["text"] for r in rows]); ids = [r["store_id"] for r in rows]
d = load(); meta, n, pct, pct_all, *_ = store_features(d)
T = pct_all.reindex(ids).fillna(0.5).values
res = []
for tag in ["느좋", "감성 모임", "데이트·기념일", "가성비 감성", "혼밥 감성", "가성비 혼밥", "카공·스터디 모임", "조용한 작업 공간"]:
    idx = [i for i, r in enumerate(rows) if tag in r["answers"]]
    y = np.array([rows[i]["answers"][tag] == "yes" for i in idx])
    if min(y.sum(), (~y).sum()) < 5: continue
    cv = StratifiedKFold(5, shuffle=True, random_state=0); r_ = {"tag": tag, "n": len(idx)}
    for name, F in [("테마점수", T[idx]), ("임베딩", X[idx]), ("둘다", np.hstack([X[idx], T[idx] * 3]))]:
        p = cross_val_predict(LogisticRegression(max_iter=2000, C=1.0), F, y, cv=cv)
        r_[name] = round((p == y).mean(), 2)
    res.append(r_)
df = pd.DataFrame(res); print(df.to_string(index=False))
w = df.n
print("가중 평균:", {c: round((df[c] * w).sum() / w.sum(), 2) for c in ["테마점수", "임베딩", "둘다"]})
