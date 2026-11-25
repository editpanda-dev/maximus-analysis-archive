# -*- coding: utf-8 -*-
"""5회차 후보에 단체 회식 좁은 정의와 경계 가게를 더한다 (2026-11-18).

단체 회식 정의를 좁힌다. 다른 목적 태그와 겹치지 않게 한다.
  1명 → 가성비 혼밥·혼밥 감성 / 2명 특별한 날 → 데이트·기념일 / 3~6명 분위기·대화 → 감성 모임 / 8명 이상 → 단체 회식
인원만으로는 감성 모임과 단체 회식이 갈리지 않아(11-18 피드백) 자리·먹는 방식·소리 세 기준을 쓰고 둘은 배타로 둔다.
팀 라벨(team1)에서 한별·우진이 같이 '예'라고 한 곳은 고깃집·횟집·뷔페·룸 참치집·넓은 치킨/피자집이었다.
대부분 70㎡ 이상이고 '단체모임 하기 좋아요'·'매장이 넓어요' 칩이 붙어 있었다.

추가 표본(kind="group", 감성 모임·단체 회식 둘을 묻는다. 모델 판정은 가린다):
  strong 10 : 단체 신호(단체모임 칩·넓어요 칩·룸 칩·면적의 전체 순위 평균) 상위 5%
  border  6 : 단체 신호 60~90% 구간
  moim    4 : 대화·모임 테마 상위 20%인데 40㎡ 미만 → 감성 모임과의 경계 확인
이전 회차·팀 세트·기존 5회차 가게는 뺀다. 기존 5회차 85곳은 그대로 두고 단체 회식 설명만 바꾼다.

실행: ~/.venvs/maximus/bin/python 분석/build_r5_group.py <5회차 후보.json> [이전 후보.json ...]
입력 파일을 제자리에서 고친다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import ROOT, SEED, area_features, evidence, load, store_features  # noqa: E402
from build_tags_v4 import group_score  # noqa: E402

STORE = ROOT / "데이터/가공/store_level"
TEAM = ROOT / "데이터/검토/store_level/label_pages/team/team_candidates.json"
# 감성 모임과 단체 회식은 서로 겹치지 않는다(한 가게에 둘 다 '예' 금지). 볼 수 있는 근거(자리·먹는 방식·소리)로 가른다.
GROUP_DESC = ("회사 부서·동아리 8명 이상이 예약해 한자리에 앉는 회식 자리. 세 가지가 다 맞아야 '예': "
              "① 단체석·룸·큰 홀이 있다(칩·리뷰에 단체·회식·룸, 대략 70㎡ 이상) "
              "② 고기·전골·회·뷔페처럼 가운데 놓고 나눠 먹는다 ③ 떠들고 건배해도 괜찮다. "
              "감성 모임과 둘 다 맞으면 하나만 '예': '부서 10명이 금요일 예약 전화하면 반길 곳'이면 단체 회식")
MOIM_DESC = ("친구 3~6명이 분위기 좋은 곳에서 오래 이야기하는 자리. 세 가지가 다 맞아야 '예': "
             "① 작은 테이블 위주 ② 인테리어·조명·음악이 가게를 고르는 이유 ③ 와인·칵테일·디저트·플레이트처럼 조금씩 시켜 오래 머문다. "
             "단체 회식과 둘 다 맞으면 하나만 '예': '친구 넷이 사진 찍고 두세 시간 얘기하러 고를 곳'이면 감성 모임")
N = {"strong": 10, "border": 6, "moim": 4}


def main(r5_path: Path, prev: list[Path]):
    rng = np.random.default_rng(SEED + 518)
    r5 = json.loads(r5_path.read_text())
    if any(s["kind"] == "group" for s in r5["stores"]):
        sys.exit("이미 group 가게가 들어 있음. 원본으로 되돌린 뒤 다시 실행")
    d = load()
    meta, n, pct_cat, pct_all, _, _ = store_features(d)
    area = area_features(meta)
    # v3는 Jev 있는 4,804곳뿐이라 가게 정보·제외 표시는 v2(전체)에서 읽는다
    v2 = pd.read_csv(STORE / "store_tags_v2.csv", keep_default_na=False).set_index("store_id").reindex(meta.index)
    score = group_score(d, meta, area)

    seen = {s.get("store_id", s["id"]) for p in prev + [r5_path] for s in json.loads(p.read_text())["stores"]}
    seen |= {s["id"] for s in json.loads(TEAM.read_text())["stores"]}
    ok = ~meta.index.isin(seen) & (v2.excluded.astype(str) == "False")
    pools = {
        "strong": meta.index[ok & (score >= score.quantile(0.95))],
        "border": meta.index[ok & score.between(score.quantile(0.6), score.quantile(0.9))],
        "moim": meta.index[ok & (pct_all["대화·모임"] >= 0.8) & (area.area_m2 < 40)],
    }
    n_by = pd.Series(n, index=meta.index)
    added = []
    for sub, pool in pools.items():
        for sid in rng.choice(pool, size=min(N[sub], len(pool)), replace=False):
            r = v2.loc[sid]
            chips, snippets = evidence(d, meta, sid, n_by[sid], pct_cat)
            a = area.area_m2.get(sid)
            added.append({
                "id": sid, "store_id": sid, "kind": "group", "group_pool": sub,
                "name": r.store_name, "naver_name": meta.at[sid, "naver_place_name"], "area": meta.at[sid, "area_name"],
                "category": r.category, "naver_reviews": int(float(meta.at[sid, "naver_review_total"] or 0)),
                "collected": int(n_by[sid]), "place_url": f"https://m.place.naver.com/restaurant/{meta.at[sid, 'place_id']}/home",
                "area_m2": None if pd.isna(a) else round(float(a)),
                "lic_uptae": None if pd.isna(area.lic_uptae.get(sid)) else area.lic_uptae.get(sid),
                "rep_menu": r.rep_menu, "signature_menu": r.signature_menu, "flags": r["flags"],
                "chips": chips, "snippets": snippets, "ask": ["감성 모임", "단체 회식"],
                "claims": [{"tag": "감성 모임", "claim": None}, {"tag": "단체 회식", "claim": None}],
                "model": {"group_score": round(float(score[sid]), 3)},
            })
    stores = r5["stores"] + added
    r5["stores"] = [stores[i] for i in rng.permutation(len(stores))]
    for t in r5["tags"]:
        t["desc"] = {"단체 회식": GROUP_DESC, "감성 모임": MOIM_DESC}.get(t["name"], t["desc"])
    r5_path.write_text(json.dumps(r5, ensure_ascii=False, indent=1))
    print(f"5회차 {len(r5['stores'])}곳 (기존 {len(stores) - len(added)} + 단체 {len(added)}: "
          + ", ".join(f"{k} {sum(s['group_pool'] == k for s in added)}" for k in N) + ")")
    for s in added:
        print(f"  [{s['group_pool']}] {s['name']} | {s['category']} | {s['area_m2']}㎡ | 신호 {s['model']['group_score']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]])
