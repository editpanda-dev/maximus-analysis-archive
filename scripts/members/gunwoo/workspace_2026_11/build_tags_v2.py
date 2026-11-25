# -*- coding: utf-8 -*-
"""태그 v2: 3회차 라벨(2026-11-15)과 메모 반영.

3회차 답은 '내 판정이 맞나'가 아니라 '이 태그에 해당하나'(예/아니오)로 읽는다.
  ('느좋 아님' 판정에 아니오 = 느좋 아님. 교촌·완백부대찌개 메모와 맞는 해석. 페이지 문구도 예/아니오로 바꿨다.)

바뀐 것
  느좋: 1·3회차 라벨 223개로 다시 맞춤. 특징 = 감성·조용·특별함(+), 가성비(−) 전체 순위.
        5겹 교차검증 AUC 0.89. 임계 0.6(정밀 0.86·재현 0.80). v1 임계 0.8은 너무 빡빡했다(아님 판정의 36%가 느좋).
        프랜차이즈(분석/build_franchise_flags.py, 전국 상호·지점명 기준)는 0.85 이상만 느좋. 라벨상 프랜차이즈 느좋 비율 23%.
  제외: 배달·포장 전문, 공간 대여, 감성주점 + 유흥 의심(상호에 혼술바·헌팅·부킹 등, 리뷰에 헌팅·부킹).
  업종 보정: 백반/한정식 등으로 잡혔는데 고기 칩·고기 메뉴가 많으면 고깃집으로 보고 허용표를 적용.
  혼밥 감성: 3회차 정밀도 47%. 틀린 곳은 특별함·대화가 높은 데이트·모임형이었다.
            → 특별함·대화 전체 순위 0.6 미만이고 데이트·기념일과 겹치지 않을 때만.
  새 태그: 야장·야외석(리뷰에 야장·테라스·루프탑 등 2회 이상, 여름 가중은 순위 단계에서),
          이색 체험(직접 구워 먹기·셀프·체험·컨셉 등 3회 이상 또는 '컨셉이 독특해요' 10% 이상).

출력: 데이터/가공/store_level/store_tags_v2.csv, <4회차 후보.json>
실행: ~/.venvs/maximus/bin/python 분석/build_tags_v2.py <라벨 폴더> <4회차 후보.json> [이전 후보.json ...]
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import ROOT, SEED, area_features, evidence, load, store_features  # noqa: E402
from build_tag_review_csv import MEAT, TAGS, exclude_flags  # noqa: E402
from build_tags_v1 import CAFE_MENU, MENU, REVIEW, read_labels  # noqa: E402

OUT = ROOT / "데이터/가공/store_level/store_tags_v2.csv"
FRANCHISE = ROOT / "데이터/가공/store_level/store_franchise_v1.csv"
SNAPSHOT = ROOT / "데이터/캐시/naver_reviews/crawler_snapshot.db"  # build_naver_reviews.py가 뜬 사본
VIBE_FEATS = {"감성·인테리어·뷰": "분위기·인테리어", "조용·아늑": "조용·아늑", "특별함": "특별함", "가성비·양": "가성비"}
VIBE_TH, FR_VIBE_TH = 0.6, 0.85
# 11-17: 칩 달린 리뷰 20건(=수집 상한) 기준이면 1.1만 곳만 남는다. 15건으로 2.2만 곳.
# 같은 라벨로 교차검증 AUC 0.892→0.890, 처음 보는 4회차 0.794→0.791, 겹치는 1.1만 곳 느좋 판정 99% 일치.
V2_MIN_N = 10  # 11-24 15→10 (build_label_round.MIN_N과 맞춤)
EXCLUDE = ("배달", "공간", "감성주점")
# 4회차 확인(11-15): '클럽'(스페인클럽·샌드위치클럽 등)과 '합석'(일반 식당 리뷰)은 유흥이 아닌 곳만 잡아서 뺐다
NIGHTLIFE_NAME = r"혼술바|헌팅|부킹|감성주점|룸살롱|나이트클럽"
NIGHTLIFE_TEXT = r"헌팅|부킹"
MEAT_MENU = r"삼겹|목살|항정|가브리|갈비|껍데기|차돌|우삼겹|대패"
OUTDOOR = r"야장|테라스|루프탑|노상|야외\s?(?:좌석|테이블|자리)"
# 4회차 메모(11-16): 고깃집은 원래 직접 구워 먹는 곳이라 굽기·셀프·화로는 이색 근거가 아니다(고깃집 8곳 중 3곳만 해당)
FUN_GRILL = r"직접 구워|구워 ?먹|셀프|화로"
FUN_OTHER = r"체험|이색|독특|특이|신기|재밌|재미있|컨셉"
FUN = FUN_GRILL + "|" + FUN_OTHER
NEW_TAGS = {"야장·야외석": "야장·테라스·루프탑 등 바깥 자리에서 먹고 마시기 좋은 곳 (여름 가중 예정)",
            "이색 체험": "직접 구워 먹기·셀프·컨셉처럼 먹는 방식이나 공간이 재미있는 곳"}
ROUND = 4
PICK = {"느좋_경계": 15, "느좋_프랜차이즈": 6, "야장·야외석": 10, "이색 체험": 10, "혼밥 감성": 8, "유흥 제외": 6}


def naver_menus(store_ids):
    """네이버 메뉴판에서 rep_menu·signature_menu 채우기 (리뷰 기반 후보가 없는 점포용). 대표 메뉴 우선, 최대 3개."""
    con = sqlite3.connect(f"file:{SNAPSHOT}?mode=ro", uri=True)
    m = pd.read_sql("select store_id, name, is_repr, menu_order from place_menus", con)
    con.close()
    m = m[m.store_id.isin(store_ids)].sort_values(["store_id", "is_repr", "menu_order"], ascending=[True, False, True])
    rep = m.groupby("store_id").name.apply(lambda s: ", ".join(s.head(3)))
    sig = m[m.is_repr == 1].groupby("store_id").name.apply(lambda s: ", ".join(s.head(3)))
    return pd.DataFrame({"rep_menu": rep, "signature_menu": sig}).reindex(store_ids).fillna("")


def vibe_model(pct_all, labels):
    X = pct_all[list(VIBE_FEATS)]
    y = labels[labels.index.isin(X.index)]
    m = LogisticRegression(max_iter=500).fit(X.loc[y.index], y)
    return pd.Series(m.predict_proba(X)[:, 1], index=X.index), dict(zip(VIBE_FEATS, m.coef_[0]))


def pct_txt(p):
    return f"상위 {max(1, round(100 - p * 100))}%"


def main(label_dir: Path, out_json: Path, prev: list[Path]):
    rng = np.random.default_rng(SEED + ROUND)
    d = load()
    meta, n, pct, pct_all, hit, evid = store_features(d, min_n=V2_MIN_N)
    cat = meta.category_small
    area = area_features(meta)
    allow = pd.read_csv(REVIEW / "tag_category_allow_v0.csv", keep_default_na=False)
    allow["final"] = np.where(allow.feedback.str.strip() != "", allow.feedback.str.strip(), allow.proposal)
    verdict = allow.set_index(["tag", "category"]).final.to_dict()
    ex = pd.read_csv(REVIEW / "store_exclude_candidates_v0.csv", keep_default_na=False)
    flags = ex[~ex.flag.str.startswith("프랜차이즈")].groupby("store_id").flag.agg(list).to_dict()
    fr = pd.read_csv(FRANCHISE, keep_default_na=False).drop_duplicates("store_id").set_index("store_id")
    menu_rv = pd.read_csv(MENU, index_col=0, keep_default_na=False)
    new = meta.index.difference(menu_rv.index)  # 리뷰 메뉴 후보·제외 후보 검토(11-13) 뒤에 들어온 점포
    if len(new):
        ex = pd.concat([ex, pd.DataFrame(exclude_flags(d, meta.loc[new], pct_all))], ignore_index=True)
        flags = ex[~ex.flag.str.startswith("프랜차이즈")].groupby("store_id").flag.agg(list).to_dict()
        menu_rv = pd.concat([menu_rv, naver_menus(new)])
        print(f"새 점포 {len(new):,}곳: 제외 플래그는 같은 규칙으로 계산, 메뉴는 네이버 메뉴판(대표 메뉴 우선)")
    menu = menu_rv.reindex(meta.index).fillna("")
    cafe_like = menu.rep_menu.str.contains(CAFE_MENU)

    dd = d[d.store_id.isin(meta.index)]
    txt = dd.groupby("store_id").review_text.apply(lambda s: " ".join(s.fillna("")))
    outdoor = txt.str.count(OUTDOOR).reindex(meta.index).fillna(0)
    fun = txt.str.count(FUN).reindex(meta.index).fillna(0)
    fun_other = txt.str.count(FUN_OTHER).reindex(meta.index).fillna(0)
    night_txt = txt.str.count(NIGHTLIFE_TEXT).reindex(meta.index).fillna(0)
    chip_share = lambda c: dd.chips.map(lambda ch: c in ch).groupby(dd.store_id).mean().reindex(meta.index)  # noqa: E731
    concept, meat_chip = chip_share("컨셉이 독특해요"), chip_share("고기 질이 좋아요")

    prob, coef = vibe_model(pct_all, read_labels(label_dir))
    rows = []
    for sid in meta.index:
        c0, fl = cat[sid], list(flags.get(sid, []))
        name = str(meta.at[sid, "store_name"])
        if re.search(NIGHTLIFE_NAME, name) or night_txt[sid] >= 1:
            fl.append("유흥 의심")
        is_fr = bool(fr.franchise.get(sid, False))
        if is_fr:
            fl.append(f"프랜차이즈({fr.brand.get(sid)})")
        meat_like = c0 not in MEAT and (meat_chip[sid] >= 0.4 or bool(re.search(MEAT_MENU, menu.rep_menu[sid])))
        c = "돼지고기 구이/찜" if meat_like else c0
        if meat_like:
            fl.append("업종 보정(고깃집)")
        excluded = [f for f in fl if f.startswith(EXCLUDE) or f == "유흥 의심"]

        tags, why = [], {}
        top = sorted(["감성·인테리어·뷰", "조용·아늑", "특별함"], key=lambda t: -pct_all.at[sid, t])[:2]
        vreason = ", ".join(f"{VIBE_FEATS[t]} {pct_txt(pct_all.at[sid, t])}" for t in top)
        th = FR_VIBE_TH if is_fr else VIBE_TH
        if excluded:
            vibe, vwhy = False, f"제외({excluded[0]})"
        else:
            vibe = prob[sid] >= th
            vwhy = vreason + (" · 프랜차이즈라 기준 높임" if is_fr else "") + ("" if vibe else " → 기준 미달")

        for t, (ts, _) in TAGS.items():
            if excluded or not hit.loc[sid, ts].all():
                continue
            v = verdict.get((t, c), "허용")
            note = ""
            if t in ("카공·스터디 모임", "조용한 작업 공간"):
                if not cafe_like[sid]:
                    continue
                v, note = "허용", "메뉴가 카페형"
            if v == "차단" or (v == "검토" and pct.loc[sid, ts].min() < 0.9):
                continue
            a = area.area_m2.get(sid)
            if t == "단체 회식" and pd.notna(a) and a < 40:
                continue
            if t == "혼밥 감성" and (pct_all.at[sid, "특별함"] >= 0.6 or pct_all.at[sid, "대화·모임"] >= 0.6):
                continue
            tags.append(t)
            why[t] = " · ".join(filter(None, [", ".join(f"{x} 업종 안 {pct_txt(pct.at[sid, x])}" for x in ts), note,
                                              f"면적 {a:.0f}㎡" if t == "단체 회식" and pd.notna(a) else ""]))
        if "혼밥 감성" in tags and "데이트·기념일" in tags:  # 메모: 혼밥 감성과 데이트는 겹치지 않게
            tags.remove("혼밥 감성")
            why.pop("혼밥 감성")
        if not excluded and outdoor[sid] >= 2:
            tags.append("야장·야외석")
            why["야장·야외석"] = f"리뷰에 야장·테라스·루프탑 등 {int(outdoor[sid])}회"
        nfun = fun_other[sid] if c in MEAT else fun[sid]
        if not excluded and (nfun >= 3 or concept[sid] >= 0.1):
            tags.append("이색 체험")
            why["이색 체험"] = f"리뷰에 직접 구워 먹기·셀프·컨셉 등 {int(nfun)}회, '컨셉이 독특해요' {concept[sid]:.0%}"
        rows.append({"store_id": sid, "store_name": name, "category": c0, "category_used": c,
                     "vibe_prob": round(float(prob[sid]), 3), "느좋": vibe, "느좋_이유": vwhy,
                     "tags": "|".join(tags), "tag_reasons": json.dumps(why, ensure_ascii=False),
                     "flags": "|".join(fl), "franchise": is_fr, "excluded": bool(excluded),
                     "rep_menu": menu.rep_menu[sid], "signature_menu": menu.signature_menu[sid]})
    out = pd.DataFrame(rows).set_index("store_id")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, encoding="utf-8-sig")

    # 4회차: 바뀐 규칙·새 태그를 예/아니오로 확인
    skip = {s["id"] for p in prev for s in json.loads(p.read_text())["stores"]}
    pool = out[~out.index.isin(skip)]
    groups = {
        "느좋_경계": pool.index[~pool.excluded & ~pool.franchise & pool.vibe_prob.between(0.5, 0.75)],
        "느좋_프랜차이즈": pool.index[pool.franchise & ~pool.excluded & (pool.vibe_prob >= 0.6)],
        "야장·야외석": pool.index[pool.tags.str.contains("야장")],
        "이색 체험": pool.index[pool.tags.str.contains("이색")],
        "혼밥 감성": pool.index[pool.tags.str.contains("혼밥 감성")],
        "유흥 제외": pool.index[pool["flags"].str.contains("유흥")],
    }
    pick = []
    for g, k in PICK.items():
        ids = [s for s in groups[g] if s not in pick]
        pick += list(rng.choice(ids, size=min(k, len(ids)), replace=False))
    n_by = pd.Series(n, index=meta.index)
    stores = []
    for sid in rng.permutation(pick):
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
            "ask": [c["tag"] for c in claims], "claims": claims, "model": {"느좋": float(r.vibe_prob)},
        })
    tags = [{"name": "느좋", "desc": "분위기가 좋아서 '여기 느낌 좋다'고 추천할 만한 곳"}] + \
           [{"name": k, "desc": v[1]} for k, v in TAGS.items()] + [{"name": k, "desc": v} for k, v in NEW_TAGS.items()]
    out_json.write_text(json.dumps({"round": ROUND, "mode": "confirm", "tags": tags, "stores": stores},
                                   ensure_ascii=False, indent=1))
    print("느좋 계수", {k: round(v, 2) for k, v in coef.items()})
    print(f"전체 {len(out):,}곳: 느좋 {int(out['느좋'].sum()):,}곳, 제외 {int(out.excluded.sum()):,}곳, "
          f"프랜차이즈 {int(out.franchise.sum()):,}곳, 태그 1개 이상 {(out.tags != '').sum():,}곳")
    print(out.tags.str.split("|").explode().replace("", np.nan).dropna().value_counts().to_string())
    print(f"{ROUND}회차 확인 {len(stores)}곳, 질문 {sum(len(s['claims']) for s in stores)}개 → {out_json}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), [Path(p) for p in sys.argv[3:]])
