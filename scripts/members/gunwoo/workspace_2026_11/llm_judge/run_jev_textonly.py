# -*- coding: utf-8 -*-
"""칩 리뷰가 적은 가게(10건 미만)를 리뷰 본문만으로 Jev 원자 판단 15개에 묻는다 (2026-11-24).

태그 모형(v5)은 칩 비율 순위가 피처라 칩 리뷰 10건 이상인 가게에만 쓴다. 그 밖의 가게 중 글 리뷰(30자 이상)가 3건 이상인 곳은
칩 줄 없이(있으면 건수만) 본문 발췌로 묻는다. 질문은 run_jev_all.py와 같다.
대상: 네이버 매칭이 맞는 식사 점포(dining_store_by_area.usable) 중 v5 대상이 아니고 글 리뷰 3건 이상.
실행: ~/.venvs/maximus/bin/python 분석/llm_judge/run_jev_textonly.py [--limit N]
출력: 데이터/검토/store_level/llm_judge/jev_textonly.jsonl, 데이터/가공/store_level/jev_atomic_textonly_v1.csv
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parents[1]))
from build_label_round import ROOT, area_features  # noqa: E402
from build_tags_v1 import MENU  # noqa: E402
from run_jev_all import ask, key  # noqa: E402

RAW = ROOT / "데이터/검토/store_level/llm_judge/jev_textonly.jsonl"
OUT = ROOT / "데이터/가공/store_level/jev_atomic_textonly_v1.csv"
CLEAN = ROOT / "데이터/가공/naver_reviews/dining_reviews_clean.csv"
TAGGED = ROOT / "데이터/가공/store_level/store_tags_v5.csv"
MIN_TEXT = 3


def targets():
    sa = pd.read_csv(ROOT / "데이터/가공/naver_reviews/dining_store_by_area.csv").drop_duplicates("store_id")
    usable = set(sa[sa.usable.astype(str) == "True"].store_id)
    tagged = set(pd.read_csv(TAGGED, usecols=[0]).iloc[:, 0])
    d = pd.read_csv(CLEAN, dtype=str, keep_default_na=False, encoding="utf-8-sig",
                    usecols=["store_id", "store_name", "category_small", "keywords", "review_text"])
    d = d[d.store_id.isin(usable - tagged)]
    d["long"] = d.review_text.str.len() > 30
    ok = d.groupby("store_id").long.sum()
    return d[d.store_id.isin(ok[ok >= MIN_TEXT].index)]


def states(d):
    meta = d.drop_duplicates("store_id").set_index("store_id")
    area = area_features(meta)
    menu = pd.read_csv(MENU, index_col=0, keep_default_na=False).rep_menu.to_dict()
    for sid, sub in d.groupby("store_id"):
        revs = [t.replace("\n", " ")[:160] for t in sub.review_text if len(t) > 30][:10]
        n_chip = int((sub.keywords != "").sum())
        a = area.loc[sid]
        m2 = f"{a.area_m2:.0f}" if pd.notna(a.area_m2) else "-"
        yield sid, (f"가게: {sub.store_name.iloc[0]} / 업종: {sub.category_small.iloc[0]} / 면적: {m2}㎡ / "
                    f"인허가 업태: {a.lic_uptae if pd.notna(a.lic_uptae) else '-'}\n"
                    f"대표 메뉴(리뷰 언급): {menu.get(sid) or '-'}\n"
                    f"리뷰 키워드 칩: 칩을 고른 리뷰가 {n_chip}건뿐이라 비율은 생략\n"
                    "리뷰 발췌:\n- " + "\n- ".join(revs))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
    RAW.parent.mkdir(parents=True, exist_ok=True)
    old = [json.loads(l) for l in open(RAW)] if RAW.exists() else []
    good = {r["store_id"]: r for r in old if r["response"]}
    todo = [s for s in states(targets()) if s[0] not in good]
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
    print(f"성공 {len(good)}곳 · 이번 실패 {len(fail)}곳{' (' + fail[0]['error'] + ')' if fail else ''} · 입력 토큰 {tok:,}")


if __name__ == "__main__":
    main()
