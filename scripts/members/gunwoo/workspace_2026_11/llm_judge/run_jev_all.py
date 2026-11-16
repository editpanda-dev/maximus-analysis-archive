# -*- coding: utf-8 -*-
"""리뷰 점수가 있는 전 점포에 Jev 원자 판단 15개(jev_questions.ATOMIC)를 묻는다.

판단은 Jev, 태그 결정은 코드(분석/build_tags_v3.py의 로지스틱). 요청 원문·응답을 jsonl로 남겨 다시 돌릴 수 있다.
실패한 호출은 오류로 남기고 다시 실행하면 그 점포만 재시도한다(아니오로 치지 않는다).
보내는 것: 가게 이름·업종·면적·인허가 업태·대표 메뉴·칩 비율·리뷰 발췌 10개(닉네임 없음).
키: ~/.config/maximus/jev.env 의 TYPESAFE_API_KEY (또는 JEV_API_KEY)
실행: ~/.venvs/maximus/bin/python 분석/llm_judge/run_jev_all.py [--limit N]
출력: 데이터/검토/store_level/llm_judge/jev_all.jsonl, 데이터/가공/store_level/jev_atomic_v1.csv
"""
import argparse, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parents[1]))
from build_label_round import ROOT, area_features, load, store_features  # noqa: E402
from build_tags_v1 import MENU  # noqa: E402
from jev_questions import ATOMIC  # noqa: E402

RAW = ROOT / "데이터/검토/store_level/llm_judge/jev_all.jsonl"
OUT = ROOT / "데이터/가공/store_level/jev_atomic_v1.csv"
QUESTIONS = {"atom_" + k: {"type": "noul", "instructions": v} for k, v in ATOMIC.items()}


def key():
    for line in open(Path.home() / ".config/maximus/jev.env"):
        k, _, v = line.strip().partition("=")
        if k in ("TYPESAFE_API_KEY", "JEV_API_KEY") and v:
            return v
    raise SystemExit("jev.env에 키 없음")


def states():
    d = load()
    meta, *_ = store_features(d)
    area = area_features(meta)
    menu = pd.read_csv(MENU, index_col=0, keep_default_na=False).rep_menu.to_dict()
    for sid, sub in d[d.store_id.isin(meta.index)].groupby("store_id"):
        chips = pd.Series([c for cs in sub.chips for c in cs]).value_counts()
        chip_txt = ", ".join(f"{k} {round(v / len(sub) * 100)}%" for k, v in chips.head(12).items())
        revs = [t.replace("\n", " ")[:160] for t in sub.review_text if len(t) > 30][:10]
        a = area.loc[sid]
        m2 = f"{a.area_m2:.0f}" if pd.notna(a.area_m2) else "-"
        yield sid, (f"가게: {sub.store_name.iloc[0]} / 업종: {sub.category_small.iloc[0]} / 면적: {m2}㎡ / "
                    f"인허가 업태: {a.lic_uptae if pd.notna(a.lic_uptae) else '-'}\n"
                    f"대표 메뉴(리뷰 언급): {menu.get(sid) or '-'}\n리뷰 키워드 칩(리뷰 {len(sub)}개 중 비율): {chip_txt}\n"
                    "리뷰 발췌:\n- " + "\n- ".join(revs))


def ask(item, k):
    sid, state = item
    body = {"model": "jev-latest", "state": state, "questions": QUESTIONS}
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + k})
    try:
        return {"store_id": sid, "request": body, "response": json.load(urllib.request.urlopen(req, timeout=120)), "error": None}
    except Exception as e:  # noqa: BLE001
        return {"store_id": sid, "request": body, "response": None, "error": str(e)[:300]}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    old = [json.loads(l) for l in open(RAW)] if RAW.exists() else []
    good = {r["store_id"]: r for r in old if r["response"]}
    todo = [s for s in states() if s[0] not in good]
    if a.limit:
        todo = todo[:a.limit]
    k = key()
    print(f"이미 {len(good)}곳, 이번 {len(todo)}곳")
    with ThreadPoolExecutor(8) as ex:
        new = list(ex.map(lambda it: ask(it, k), todo))
    for r in new:
        if r["response"]:
            good[r["store_id"]] = r
    with open(RAW, "w") as f:
        for r in good.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    fail = [r for r in new if not r["response"]]
    rows = [{"store_id": s, **{q[5:]: v["noul"] for q, v in r["response"]["answers"].items()}} for s, r in good.items()]
    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")
    tok = sum(r["response"]["usage"]["input_tokens"] for r in good.values())
    print(f"성공 {len(good)}곳 · 이번 실패 {len(fail)}곳{' (' + fail[0]['error'] + ')' if fail else ''} · 입력 토큰 누적 {tok:,}")


if __name__ == "__main__":
    main()
