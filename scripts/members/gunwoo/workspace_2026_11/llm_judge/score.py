import json, sys, collections
for p in sys.argv[1:]:
    ok = collections.defaultdict(list); err = 0
    for l in open(p):
        j = json.loads(l)
        if "_err" in j["pred"]: err += 1; continue
        for t, a in j["answers"].items():
            v = str(j["pred"].get(t, "no")).lower()
            ok[t].append((v.startswith("y")) == (a == "yes"))
    allv = [x for v in ok.values() for x in v]
    print(f"{p.split('/')[-1]}: 정확도 {sum(allv)/len(allv):.2f} (질문 {len(allv)}, 오류 {err})  " +
          " · ".join(f"{t} {sum(v)/len(v):.2f}({len(v)})" for t, v in sorted(ok.items(), key=lambda x: -len(x[1]))))
