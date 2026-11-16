"""Jev(TypeSafe) 판정. POST https://api.typesafe.ai/v1/systemone, 키 TYPESAFE_API_KEY.
같은 평가셋(앞 8곳 제외). 요청 원문을 같이 저장해 다시 돌릴 수 있게 한다. 실패는 오류로 남긴다(no로 치지 않음).
python run_jev.py <eval.json> <out.jsonl> [--limit N]"""
import json, os, sys, urllib.request, argparse
sys.path.insert(0, os.path.dirname(__file__)); from jev_questions import questions
ap = argparse.ArgumentParser(); ap.add_argument("eval"); ap.add_argument("out"); ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
rows = json.load(open(a.eval))["rows"][8:]
if a.limit: rows = rows[:a.limit]
key = os.environ["TYPESAFE_API_KEY"]
done = {json.loads(l)["store_id"] for l in open(a.out)} if os.path.exists(a.out) else set()
with open(a.out, "a") as f:
    for i, r in enumerate(rows):
        if r["store_id"] in done: continue
        body = {"model": "jev-latest", "state": r["text"], "questions": questions(list(r["answers"]))}
        req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "Authorization": "Bearer " + key})
        try: res = json.load(urllib.request.urlopen(req, timeout=120)); err = None
        except Exception as e: res, err = None, str(e)[:300]
        f.write(json.dumps({"store_id": r["store_id"], "answers": r["answers"], "request": body, "response": res, "error": err}, ensure_ascii=False) + "\n"); f.flush()
        if i % 20 == 0: print(i, len(rows), err or "", flush=True)
