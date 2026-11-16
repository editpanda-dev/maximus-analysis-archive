# -*- coding: utf-8 -*-
"""팀원용 라벨 세트: 라벨러 간 일치율을 재려고 건우가 찍은(찍을) 가게와 같은 가게·같은 질문을 모델 판정 없이 묻는다.

구성: 건우가 1·3회차에 찍은 가게 30곳(느좋 예·아니오 반반) + 5회차 무작위 25곳(건우도 5회차에서 찍음).
실행: ~/.venvs/maximus/bin/python 분석/build_team_label_set.py <라벨·후보 폴더> <출력.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

N_EACH = 15


def main(src: Path, out: Path):
    rng = np.random.default_rng(7)
    cand, tags = {}, {}
    for f in ["candidates.json", "candidates_r2.json", "candidates_r3.json", "candidates_r4.json", "candidates_r5.json"]:
        j = json.loads((src / f).read_text())
        tags.update({t["name"]: t["desc"] for t in j["tags"]})
        for s in j["stores"]:
            cand.setdefault(s.get("store_id", s["id"]), s)
    r5 = json.loads((src / "candidates_r5.json").read_text())["stores"]
    yes, no = [], []
    for f in sorted(src.glob("semas:*.json")):
        j = json.loads(f.read_text())
        a = {t: v for t, v in j.get("answers", {}).items() if v in ("yes", "no")}
        if j["store_id"] in cand and "느좋" in a:
            (yes if a["느좋"] == "yes" else no).append((j["store_id"], list(a)))
    pick = [yes[i] for i in rng.choice(len(yes), N_EACH, replace=False)] + [no[i] for i in rng.choice(len(no), N_EACH, replace=False)]
    pick += [(s["store_id"], s["ask"]) for s in r5 if s["kind"] == "random"]
    stores = []
    for i in rng.permutation(len(pick)):
        sid, ask = pick[i]
        s = cand[sid]
        stores.append({**{k: s.get(k) for k in ["name", "naver_name", "area", "category", "naver_reviews", "collected", "place_url",
                                                 "area_m2", "lic_uptae", "rep_menu", "signature_menu", "chips", "snippets"]},
                       "id": sid, "flags": "", "ask": ask, "claims": [{"tag": t, "claim": None} for t in ask]})
    out.write_text(json.dumps({"round": "team1", "mode": "confirm", "tags": [{"name": k, "desc": v} for k, v in tags.items()],
                               "stores": stores}, ensure_ascii=False, indent=1))
    print(f"{len(stores)}곳, 질문 {sum(len(s['ask']) for s in stores)}개 → {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
