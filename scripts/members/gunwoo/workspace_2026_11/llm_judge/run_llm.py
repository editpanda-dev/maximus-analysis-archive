"""로컬(Ollama) 또는 OpenAI 호환 API로 라벨 질문을 판정한다. 퓨샷 = 앞 N_SHOT곳, 평가 = 나머지.
python run_llm.py <eval.json> <model> <out.jsonl> [--shots 8] [--limit 0] [--base http://localhost:11434]"""
import json, sys, time, argparse, os, re, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument("eval"); ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--shots", type=int, default=8); ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--api", default="ollama")  # ollama | openai
ap.add_argument("--base", default="http://localhost:11434"); a = ap.parse_args()
E = json.load(open(a.eval)); rows = E["rows"]; tags = E["tags"]
RULES = ("판정 기준(라벨 단 사람의 기준):\n"
 "- 느좋 = 분위기·감성·인테리어가 좋아 '여기 느낌 좋다'고 할 곳. 맛집·가성비·친절만으로는 느좋 아님. 프랜차이즈 체인점은 대부분 느좋 아님.\n"
 "- 카공·작업 공간은 실제로 공부·노트북 작업을 하는 카페형 공간. 술집에서 오래 머무는 건 해당 안 됨.\n"
 "- 단체 회식 = 여럿이 넓게 앉아 먹고 마시기 좋은 곳(고깃집·한식 단체석 등).\n"
 "- '가성비 감성', '혼밥 감성'은 두 조건을 다 갖춰야 하는 드문 조합.\n"
 "- 리뷰 근거가 약하면 no.")
SYS = "너는 서울 음식점을 목적별 태그로 분류하는 평가자다.\n태그 정의:\n" + "\n".join(f"- {k}: {v}" for k, v in tags.items()) + "\n" + RULES + \
      "\n출력은 JSON 하나: 물어본 태그마다 \"yes\" 또는 \"no\". 다른 말 금지."
shots, evals = rows[:a.shots], rows[a.shots:]
if a.limit: evals = evals[:a.limit]
def msg_for(r): return f"{r['text']}\n\n물어볼 태그: {', '.join(r['answers'])}"
base_msgs = [{"role": "system", "content": SYS}]
for r in shots:
    base_msgs += [{"role": "user", "content": msg_for(r)}, {"role": "assistant", "content": json.dumps(r["answers"], ensure_ascii=False)}]
def call(msgs):
    if a.api == "ollama":
        body = {"model": a.model, "messages": msgs, "stream": False, "think": False, **({} if "qwen" in a.model else {"format": "json"}),
                "options": {"temperature": 0, "num_ctx": 16384}}
        url, hdr = a.base + "/api/chat", {"Content-Type": "application/json"}
    else:
        body = {"model": a.model, "messages": msgs, "temperature": 0, "max_tokens": 4000}
        url = a.base + "/chat/completions"; hdr = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ[a.api.upper() + "_API_KEY"]}
    req = urllib.request.Request(url, json.dumps(body).encode(), hdr)
    j = json.load(urllib.request.urlopen(req, timeout=600))
    return j["message"]["content"] if a.api == "ollama" else j["choices"][0]["message"]["content"]
done = set()
if os.path.exists(a.out): done = {json.loads(l)["store_id"] for l in open(a.out)}
t0 = time.time()
with open(a.out, "a") as f:
    for i, r in enumerate(evals):
        if r["store_id"] in done: continue
        try:
            raw = call(base_msgs + [{"role": "user", "content": msg_for(r)}])
            pred = json.loads(re.findall(r"\{[^{}]*\}", raw)[-1])
        except Exception as e: pred = {"_err": str(e)[:200]}
        f.write(json.dumps({"store_id": r["store_id"], "answers": r["answers"], "pred": pred}, ensure_ascii=False) + "\n"); f.flush()
        if i % 10 == 0: print(f"{i}/{len(evals)} {time.time()-t0:.0f}s", flush=True)
print("done", time.time() - t0)
