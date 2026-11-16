import json, sys, collections
import pandas as pd
E = json.load(open(sys.argv[1])); ev = E["rows"][8:]
t = pd.read_csv("데이터/가공/store_level/store_tags_v2.csv", keep_default_na=False).set_index("store_id")
ok = collections.defaultdict(list); maj = collections.defaultdict(list)
cnt = collections.Counter((tg, a) for r in ev for tg, a in r["answers"].items())
for r in ev:
    if r["store_id"] not in t.index: continue
    row = t.loc[r["store_id"]]
    for tg, a in r["answers"].items():
        p = str(row["느좋"]) == "True" if tg == "느좋" else tg in row["tags"]
        ok[tg].append(p == (a == "yes"))
        m = cnt[(tg, "yes")] > cnt[(tg, "no")]
        maj[tg].append(m == (a == "yes"))
for name, D in [("태그 v2(라벨로 맞춘 규칙, 표본 안 평가)", ok), ("다수결(전부 많은 쪽)", maj)]:
    allv = [x for v in D.values() for x in v]
    print(f"{name}: 정확도 {sum(allv)/len(allv):.2f} (질문 {len(allv)})  " + " · ".join(f"{k} {sum(v)/len(v):.2f}({len(v)})" for k, v in sorted(D.items(), key=lambda x: -len(x[1]))))
