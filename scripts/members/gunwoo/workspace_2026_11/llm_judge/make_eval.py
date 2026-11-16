"""라벨(1·3회차) → 가게별 입력 텍스트 + 정답. LLM·임베딩 평가용."""
import sys, json, glob, random
import pandas as pd
sys.path.insert(0, "분석")
from build_label_round import load
SP = sys.argv[1]
docs = [json.load(open(f)) for f in glob.glob(f"{SP}/labels_dump3/labels/*.json")]
d = load()
g = d.groupby("store_id")
cand = {}
for f in ["candidates.json", "candidates_r2.json", "candidates_r3.json"]:
    j = json.load(open(f"{SP}/labeling/{f}"))
    for s in j["stores"]: cand[s["id"]] = s
tagdesc = {t["name"]: t["desc"] for t in json.load(open(f"{SP}/labeling/candidates_r4.json"))["tags"]}
rows = []
for doc in docs:
    sid = doc["store_id"]
    ans = {t: a for t, a in doc.get("answers", {}).items() if a in ("yes", "no")}
    if not ans or sid not in g.groups: continue
    sub = g.get_group(sid)
    chips = pd.Series([c for cs in sub.chips for c in cs]).value_counts()
    chip_txt = ", ".join(f"{k} {round(v/len(sub)*100)}%" for k, v in chips.head(12).items())
    revs = [t.replace("\n", " ")[:160] for t in sub.review_text if len(t) > 30][:10]
    c = cand.get(sid, {})
    text = (f"가게: {sub.store_name.iloc[0]} / 업종: {sub.category_small.iloc[0]} / 면적: {c.get('area_m2') or '-'}㎡ / 인허가 업태: {c.get('lic_uptae') or '-'}\n"
            f"대표 메뉴(리뷰 언급): {c.get('rep_menu') or '-'}\n리뷰 키워드 칩(리뷰 {len(sub)}개 중 비율): {chip_txt}\n리뷰 발췌:\n- " + "\n- ".join(revs))
    rows.append({"store_id": sid, "text": text, "answers": ans, "round": doc.get("round")})
random.Random(0).shuffle(rows)
json.dump({"tags": tagdesc, "rows": rows}, open(f"{SP}/llm/eval.json", "w"), ensure_ascii=False)
from collections import Counter
print(len(rows), "가게", sum(len(r["answers"]) for r in rows), "질문", Counter(t for r in rows for t in r["answers"]))
