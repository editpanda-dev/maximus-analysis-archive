# -*- coding: utf-8 -*-
"""태그 v1: 1회차 라벨·메모를 반영해 규칙으로 다시 판정하고, 확인용 3회차 후보를 만든다.

느좋 v1 (1회차 라벨 117개로 맞춤, 5겹 교차검증 AUC 0.90 / 옛 느좋지수 0.60):
  라벨상 느좋은 맛·친절·청결이 아니라 분위기와 특별함으로 갈렸다.
  확률 = 로지스틱(감성·조용·특별함의 전체 가게 기준 순위). VIBE_TH 이상이면 느좋.
  배달·포장 전문·공간 대여·감성주점은 제외, 프랜차이즈는 랜드마크 지점 후보만 허용.
조합 태그 v1:
  칩 근거(두 테마 모두 업종 안 상위 25% + 업종 평균 초과 + 2회 이상) 위에
  - 업종×태그 허용표(데이터/검토/store_level/tag_category_allow_v0.csv)의 판정. feedback이 있으면 그걸 따른다.
    차단 → 빼고, 검토 → 두 테마 모두 업종 안 상위 10%일 때만.
  - 카공·조용한 작업 공간은 리뷰 메뉴가 카페형(라떼·커피·디저트)인 가게에만 연다.
  - 단체 회식은 면적을 아는 가게면 40㎡ 이상만.
  - 제외 후보(배달·포장, 공간 대여, 감성주점)는 태그를 붙이지 않는다.

출력:
  데이터/가공/store_level/store_tags_v1.csv  (로컬: 가게별 태그·이유)
  <3회차 후보.json>                           (라벨링 페이지: 내 판정을 Z 맞다 / M 아니다로 확인)
실행: ~/.venvs/maximus/bin/python 분석/build_tags_v1.py <라벨 폴더> <3회차 후보.json> [제외할 이전 후보.json ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import ROOT, SEED, area_features, evidence, load, store_features  # noqa: E402
from build_tag_review_csv import TAGS  # noqa: E402

REVIEW = ROOT / "데이터/검토/store_level"
OUT = ROOT / "데이터/가공/store_level/store_tags_v1.csv"
MENU = REVIEW / "store_menu_candidates_v1_kiwi.csv"
VIBE_FEATS = {"감성·인테리어·뷰": "분위기·인테리어", "조용·아늑": "조용·아늑", "특별함": "특별함"}
VIBE_TH = 0.8
CAFE_MENU = r"라떼|커피|아메리카노|에이드|케이크|디저트|스콘|크로플|와플"
EXCLUDE = ("배달", "공간", "감성주점")
PER_TAG, VIBE_YES, VIBE_NO = 10, 25, 10


def read_labels(label_dir: Path) -> pd.Series:
    lab = {}
    for f in label_dir.glob("*.json"):
        v = json.loads(f.read_text())
        v = v.get("data", v)
        a = v.get("answers", {}).get("느좋")
        if a in ("yes", "no"):
            lab[v["store_id"]] = a == "yes"
    return pd.Series(lab, dtype=bool)


def vibe_v1(pct_all, labels):
    X = pct_all[list(VIBE_FEATS)]
    y = labels[labels.index.isin(X.index)]
    m = LogisticRegression(C=1.0).fit(X.loc[y.index], y)
    return pd.Series(m.predict_proba(X)[:, 1], index=X.index), dict(zip(VIBE_FEATS, m.coef_[0]))


def main(label_dir: Path, out_json: Path, prev: list[Path]):
    rng = np.random.default_rng(SEED + 3)
    d = load()
    meta, n, pct, pct_all, hit, evid = store_features(d)
    cat = meta.category_small
    area = area_features(meta)
    allow = pd.read_csv(REVIEW / "tag_category_allow_v0.csv", keep_default_na=False)
    allow["final"] = np.where(allow.feedback.str.strip() != "", allow.feedback.str.strip(), allow.proposal)
    verdict = allow.set_index(["tag", "category"]).final.to_dict()
    ex = pd.read_csv(REVIEW / "store_exclude_candidates_v0.csv", keep_default_na=False)
    flags = ex.groupby("store_id").flag.agg(list).to_dict()
    menu = pd.read_csv(MENU, index_col=0, keep_default_na=False)
    cafe_like = menu.rep_menu.str.contains(CAFE_MENU).reindex(meta.index, fill_value=False)

    prob, coef = vibe_v1(pct_all, read_labels(label_dir))
    rows = []
    for sid in meta.index:
        c, fl = cat[sid], flags.get(sid, [])
        excluded = [f for f in fl if f.startswith(EXCLUDE)]
        franchise = any(f.startswith("프랜차이즈") for f in fl)
        landmark = any("랜드마크" in f for f in fl)
        tags, why = [], {}
        # 느좋
        top = sorted(VIBE_FEATS, key=lambda t: -pct_all.at[sid, t])[:2]
        vibe_reason = ", ".join(f"{VIBE_FEATS[t]} 상위 {max(1, round(100 - pct_all.at[sid, t] * 100))}%" for t in top)
        if excluded:
            vibe, vwhy = False, f"제외 후보({excluded[0]})"
        elif franchise and not landmark:
            vibe, vwhy = False, "프랜차이즈(랜드마크 지점 아님)"
        else:
            vibe = prob[sid] >= VIBE_TH
            vwhy = vibe_reason + ("" if vibe else " → 기준 미달")
        # 조합 태그
        for t, (ts, _) in TAGS.items():
            if excluded or not hit.loc[sid, ts].all():
                continue
            v = verdict.get((t, c), "허용")
            if t in ("카공·스터디 모임", "조용한 작업 공간"):
                if not cafe_like[sid]:
                    continue
                v, note = "허용", "메뉴가 카페형"
            else:
                note = ""
            if v == "차단" or (v == "검토" and pct.loc[sid, ts].min() < 0.9):
                continue
            a = area.area_m2.get(sid)
            if t == "단체 회식" and pd.notna(a) and a < 40:
                continue
            tags.append(t)
            why[t] = " · ".join(filter(None, [
                ", ".join(f"{x} 업종 안 상위 {max(1, round(100 - pct.at[sid, x] * 100))}%" for x in ts), note,
                f"면적 {a:.0f}㎡" if t == "단체 회식" and pd.notna(a) else ""]))
        rows.append({"store_id": sid, "store_name": meta.at[sid, "store_name"], "category": c,
                     "vibe_prob": round(float(prob[sid]), 3), "느좋": vibe, "느좋_이유": vwhy,
                     "tags": "|".join(tags), "tag_reasons": json.dumps(why, ensure_ascii=False),
                     "flags": "|".join(fl), "rep_menu": menu.rep_menu.get(sid, ""),
                     "signature_menu": menu.signature_menu.get(sid, "")})
    out = pd.DataFrame(rows).set_index("store_id")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, encoding="utf-8-sig")

    # 3회차: 내 판정을 확인받을 가게 뽑기 (이전 회차 가게 제외)
    skip = {s["id"] for p in prev for s in json.loads(p.read_text())["stores"]}
    pool = out[~out.index.isin(skip)]
    pick = set()
    for t in TAGS:
        ids = [s for s in pool.index[pool.tags.str.contains(t, regex=False)] if s not in pick]
        pick |= set(rng.choice(ids, size=min(PER_TAG, len(ids)), replace=False))
    yes = [s for s in pool.index[pool["느좋"]] if s not in pick]
    pick |= set(rng.choice(yes, size=min(VIBE_YES, len(yes)), replace=False))
    near = [s for s in pool.index[~pool["느좋"] & pool.vibe_prob.between(0.55, VIBE_TH)] if s not in pick]
    pick |= set(rng.choice(near, size=min(VIBE_NO, len(near)), replace=False))

    n_by = pd.Series(n, index=meta.index)
    stores = []
    for sid in rng.permutation(sorted(pick)):
        r = out.loc[sid]
        chips, snippets = evidence(d, meta, sid, n_by[sid], pct)
        why = json.loads(r.tag_reasons)
        claims = [{"tag": "느좋", "claim": bool(r["느좋"]), "why": r["느좋_이유"]}]
        claims += [{"tag": t, "claim": True, "why": why[t]} for t in r.tags.split("|") if t]
        a = area.area_m2.get(sid)
        stores.append({
            "id": sid, "name": r.store_name, "naver_name": meta.at[sid, "naver_place_name"],
            "area": meta.at[sid, "area_name"], "category": r.category,
            "naver_reviews": int(float(meta.at[sid, "naver_review_total"] or 0)), "collected": int(n_by[sid]),
            "place_url": f"https://m.place.naver.com/restaurant/{meta.at[sid, 'place_id']}/home",
            "area_m2": None if pd.isna(a) else round(float(a)),
            "lic_uptae": None if pd.isna(area.lic_uptae.get(sid)) else area.lic_uptae.get(sid),
            "rep_menu": r.rep_menu, "signature_menu": r.signature_menu, "flags": r["flags"],
            "chips": chips, "snippets": snippets,
            "ask": [c["tag"] for c in claims], "claims": claims,
            "model": {"느좋": float(r.vibe_prob)},
        })
    tags = [{"name": "느좋", "desc": "분위기가 좋아서 '여기 느낌 좋다'고 추천할 만한 곳"}] + \
           [{"name": k, "desc": v[1]} for k, v in TAGS.items()]
    out_json.write_text(json.dumps({"round": 3, "mode": "confirm", "tags": tags, "stores": stores},
                                   ensure_ascii=False, indent=1))
    n_claims = sum(len(s["claims"]) for s in stores)
    print("느좋 계수", {k: round(v, 2) for k, v in coef.items()})
    print(f"전체 {len(out):,}곳: 느좋 {int(out['느좋'].sum()):,}곳, 태그 1개 이상 {(out.tags != '').sum():,}곳")
    print(out.tags.str.split("|").explode().replace("", np.nan).dropna().value_counts().to_string())
    print(f"3회차 확인 {len(stores)}곳, 판정 {n_claims}개 → {out_json}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])
