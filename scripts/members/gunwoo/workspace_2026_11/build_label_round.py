"""느좋·조합 태그 라벨링 회차용 후보 가게 뽑기.

입력: 데이터/가공/naver_reviews/dining_reviews_clean.csv, 저장소 테마 사전(THEME_MAP)
출력: 후보 JSON (라벨링 아티팩트가 읽음). 본문 조각은 들어가지만 닉네임은 넣지 않는다.

태그마다 모델 기준 '해당'(상위) · '경계' · '비해당'(하위) 가게를 섞어 뽑는다.
그래야 라벨로 정밀도와 놓친 비율을 함께 잴 수 있다. 화면에는 모델 점수를 보여 주지 않는다(답 유도 방지).

2회차부터 인허가 면적·업태(분석/match_localdata.py 출력)를 반영한다.
  - 대화·모임은 넓을수록, 혼자·조용·아늑은 좁을수록 점수를 AREA_W만큼 올린다(업종 안 면적 순위).
    면적만으로 태그가 생기지는 않는다: '해당'은 여전히 칩 근거(업종 평균 초과, 선택 2회 이상)가 있어야 한다.
  - 인허가 업태가 감성주점이면 느좋 점수를 절반으로 깎는다. 폐업 확인된 가게는 뽑지 않는다.
  - 면적 반영 전·후 판정이 갈리는 가게('flip')를 일부러 섞어 면적이 도움이 되는지 라벨로 잰다.
  - model 필드에 반영 전(_raw)·후 판정을 함께 남긴다.

실행:
    ~/.venvs/maximus/bin/python 분석/build_label_round.py <출력.json> [회차=1] [이전 회차 후보.json ...]
    이전 회차 후보 파일을 주면 그 가게들은 빼고 뽑는다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "maximus-analysis-archive/scripts/store_level"))
from build_keyword_theme_map_v0 import SRC, THEME_MAP, THEMES  # noqa: E402

M = 20          # 경험적 베이즈 축소 강도
MIN_N = 10      # 평가에 쓰는 최소 칩 리뷰 수. 11-24 20→10: 가게당 최대 20건만 모아서 20이면 전부 칩인 가게만 남았다
SEED = 0
# 조합 태그: 이름 → (테마들, 화면 설명)
COMBOS = {
    "감성 모임": (["감성·인테리어·뷰", "대화·모임"], "분위기 좋고 여럿이 얘기 나누며 머물기 좋은 곳"),
    "데이트·기념일": (["감성·인테리어·뷰", "특별함"], "분위기와 메뉴가 특별해 데이트·기념일에 갈 만한 곳"),
    "카공·스터디 모임": (["오래 머물기·공부", "대화·모임"], "여럿이 오래 앉아 공부·작업·회의하기 좋은 곳"),
    "조용한 작업 공간": (["조용·아늑", "오래 머물기·공부"], "조용해서 혼자 오래 집중하기 좋은 곳"),
    "가성비 혼밥": (["가성비·양", "혼자"], "혼자 부담 없이 싸고 든든하게 먹기 좋은 곳"),
    "가성비 감성": (["가성비·양", "감성·인테리어·뷰"], "가격은 착한데 분위기도 좋은 곳 (드문 조합)"),
    "혼밥 감성": (["혼자", "감성·인테리어·뷰"], "혼자 가도 편한데 분위기도 좋은 곳 (드문 조합)"),
}
VIBE_DESC = "분위기가 좋고 맛·친절·청결 기본기도 갖춰서 '여기 느낌 좋다'고 추천할 만한 곳"
PER_TAG = {1: {"pos": 8, "border": 4, "neg": 3},
           2: {"pos": 6, "border": 3, "neg": 2, "flip": 4}}
VIBE_EXTRA = {1: 15, 2: 10}
MATCH = ROOT / "데이터/가공/store_level/store_localdata_match.csv"
AREA_W = 0.3                                   # 면적 순위 반영 비중
AREA_SIGN = {"대화·모임": 1, "혼자": -1, "조용·아늑": -1}  # 넓을수록 +, 좁을수록 +
VIBE_PENALTY = {"감성주점": 0.5}               # 인허가 업태별 느좋 배수


def load():
    d = pd.read_csv(SRC, dtype=str, keep_default_na=False, encoding="utf-8-sig",
                    usecols=["store_id", "store_name", "area_name", "category_small", "place_id",
                             "naver_place_name", "naver_review_total", "keywords", "extra_tags", "review_text"])
    d["chips"] = [[x for x in f"{a}, {b}".split(", ") if x] for a, b in zip(d.keywords, d.extra_tags)]
    return d[d.chips.str.len() > 0].reset_index(drop=True)


def store_features(d, min_n=MIN_N):
    k2t = {k: v[0] for k, v in THEME_MAP.items()}
    R = np.array([[t in {x for k in ch for x in k2t.get(k, [])} for t in THEMES] for ch in d.chips], float)
    sid, idx = np.unique(d.store_id, return_inverse=True)
    C = np.zeros((len(sid), len(THEMES)))
    np.add.at(C, idx, R)
    n = np.bincount(idx, minlength=len(sid)).astype(float)
    meta = d.drop_duplicates("store_id").set_index("store_id").loc[sid]
    cat = meta.category_small.values
    mu = pd.DataFrame(C / n[:, None]).groupby(cat).transform("mean").clip(lower=1e-3).values
    P = (C + M * mu) / (n[:, None] + M)
    L = pd.DataFrame(np.log(P / mu), index=sid, columns=THEMES)
    ok = n >= min_n
    Lk = L[ok]
    pct_cat = Lk.groupby(cat[ok]).rank(pct=True)                     # 같은 업종 안 상대 순위
    pct_all = pd.DataFrame(P, index=sid, columns=THEMES)[ok].rank(pct=True)  # 전체 가게 기준 절대 순위
    # 업종 안 상위 25% + 업종 평균 초과 + 실제 선택 2회 이상일 때만 '해당'
    evid = (Lk > 0) & (pd.DataFrame(C, index=sid, columns=THEMES)[ok] >= 2)
    hit = (pct_cat >= 0.75) & evid
    return meta[ok], n[ok], pct_cat, pct_all, hit, evid


def area_features(meta):
    """가게별 인허가 면적·업태·상태. 상호가 정확히 맞거나 관리번호로 붙은 매칭만 쓴다."""
    m = pd.read_csv(MATCH, dtype={"store_id": str})
    m = m[m.match_type.isin(["exact", "id"])]
    m.index = np.where(m.store_id.str.startswith("MA"), "semas:" + m.store_id, m.store_id)
    a = m.reindex(meta.index)[["area_m2", "lic_uptae", "lic_state"]]
    a["area_pct"] = np.log(a.area_m2).groupby(meta.category_small).rank(pct=True)
    return a


def adjust(pct_cat, evid, area):
    """면적 순위를 섞은 업종 안 순위와 그 기준의 '해당' 판정. 면적 없는 가게는 그대로."""
    adj = pct_cat.copy()
    for t, sgn in AREA_SIGN.items():
        ap = area.area_pct if sgn > 0 else 1 - area.area_pct
        adj[t] = ((1 - AREA_W) * pct_cat[t] + AREA_W * ap).fillna(pct_cat[t])
    return adj, (adj >= 0.75) & evid


def vibe_score(pct_cat, pct_all):
    # 분위기는 전체 기준(치킨집 중 감성 같은 상대값 방지), 기본기는 업종 안 기준
    atm = pct_all[["감성·인테리어·뷰", "조용·아늑"]].max(axis=1)
    parts = pd.concat([atm, pct_cat["맛"], pct_cat["서비스·친절"], pct_cat["청결"]], axis=1)
    return np.exp(np.log(parts.clip(lower=1e-3)).mean(axis=1))  # 기하평균: 하나라도 낮으면 깎임


def sample(pct, hit, hit_raw, vibe, rng, round_no, skip):
    asked = {}  # store_id → set(tags)
    for name, (ts, _) in COMBOS.items():
        score = pct[ts].min(axis=1)
        allhit, rawhit = hit[ts].all(axis=1), hit_raw[ts].all(axis=1)
        groups = {
            "pos": score[allhit].sort_values(ascending=False).index[:40],
            "border": score[~allhit & (score >= 0.55)].index,
            "neg": score[score < 0.3].index,
            "flip": score[allhit != rawhit].index,  # 면적 반영으로 판정이 바뀐 가게
        }
        for g, k in PER_TAG[min(round_no, 2)].items():
            pool = [s for s in groups[g] if s not in asked and s not in skip]
            for s in rng.choice(pool, size=min(k, len(pool)), replace=False):
                asked.setdefault(s, set()).add(name)
    top_vibe = [s for s in vibe.sort_values(ascending=False).index[:200] if s not in asked and s not in skip]
    for s in rng.choice(top_vibe, size=VIBE_EXTRA[min(round_no, 2)], replace=False):
        asked.setdefault(s, set())
    return asked


def evidence(d, meta, sid, n, pct_cat):
    rows = d[d.store_id == sid]
    chips = pd.Series([c for ch in rows.chips for c in ch]).value_counts()
    cat_rows = d[d.category_small == meta.at[sid, "category_small"]]
    cat_rate = pd.Series([c for ch in cat_rows.chips for c in set(ch)]).value_counts() / len(cat_rows)
    chip_list = []
    for c, cnt in chips.items():
        rate = cnt / len(rows)
        chip_list.append({"chip": c, "share": round(rate, 2), "ratio": round(rate / cat_rate.get(c, rate), 1)})
    chip_list = sorted(chip_list, key=lambda x: (-x["ratio"] * (x["share"] >= 0.1), -x["share"]))[:8]
    texts = rows.review_text[rows.review_text.str.len() >= 20]
    texts = texts.sample(min(4, len(texts)), random_state=SEED)
    snippets = [t[:160] + ("…" if len(t) > 160 else "") for t in texts]
    return chip_list, snippets


def area_view(area, sid):
    """화면에 보여 줄 면적·업태 (없으면 None)."""
    a = area.loc[sid]
    return {"area_m2": None if pd.isna(a.area_m2) else round(float(a.area_m2)),
            "lic_uptae": None if pd.isna(a.lic_uptae) else a.lic_uptae}


def main(out: Path, round_no: int = 1, prev: list[Path] = ()):
    rng = np.random.default_rng(SEED + round_no)
    d = load()
    meta, n, pct_raw, pct_all, hit_raw, evid = store_features(d)
    area = area_features(meta)
    vibe_raw = vibe_score(pct_raw, pct_all)
    if round_no >= 2:
        pct_cat, hit = adjust(pct_raw, evid, area)
        vibe = vibe_raw * area.lic_uptae.map(VIBE_PENALTY).fillna(1.0)
        skip = {s["id"] for p in prev for s in json.loads(p.read_text())["stores"]}
        skip |= set(area.index[area.lic_state.eq("폐업")])
    else:
        pct_cat, hit, vibe, skip = pct_raw, hit_raw, vibe_raw, set()
    asked = sample(pct_cat, hit, hit_raw, vibe, rng, round_no, skip)
    n_by = pd.Series(n, index=meta.index)
    stores = []
    for sid in rng.permutation(list(asked)):
        chips, snippets = evidence(d, meta, sid, n_by[sid], pct_cat)
        place = meta.at[sid, "place_id"]
        model = {"느좋": round(float(vibe[sid]), 3),
                 **{t: bool(hit.loc[sid, COMBOS[t][0]].all()) for t in asked[sid]}}
        if round_no >= 2:  # 면적 반영 전 판정도 남겨 둘을 비교한다
            model |= {"느좋_raw": round(float(vibe_raw[sid]), 3),
                      **{f"{t}_raw": bool(hit_raw.loc[sid, COMBOS[t][0]].all()) for t in asked[sid]}}
        stores.append({
            "id": sid,
            "name": meta.at[sid, "store_name"],
            "naver_name": meta.at[sid, "naver_place_name"],
            "area": meta.at[sid, "area_name"],
            "category": meta.at[sid, "category_small"],
            "naver_reviews": int(float(meta.at[sid, "naver_review_total"] or 0)),
            "collected": int(n_by[sid]),
            "place_url": f"https://m.place.naver.com/restaurant/{place}/home",
            "chips": chips,
            "snippets": snippets,
            **area_view(area, sid),
            "ask": ["느좋"] + sorted(asked[sid]),
            "model": model,  # 모델 판정은 화면에 안 쓰고 채점용으로만 둔다
        })
    tags = [{"name": "느좋", "desc": VIBE_DESC}] + [{"name": k, "desc": v[1]} for k, v in COMBOS.items()]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"round": round_no, "tags": tags, "stores": stores}, ensure_ascii=False, indent=1))
    n_q = sum(len(s["ask"]) for s in stores)
    print(f"{round_no}회차 후보 {len(stores)}곳, 질문 {n_q}개 → {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 1, [Path(p) for p in sys.argv[3:]])
