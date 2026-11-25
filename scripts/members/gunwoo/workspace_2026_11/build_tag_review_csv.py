# -*- coding: utf-8 -*-
"""사람 검토용 CSV 두 개: ① 업종×조합 태그 허용표 ② 추천에서 뺄 가게 후보.

1회차 라벨 메모(2026-11-13) 반영:
  - '횟집·치킨·한식이 조용한 작업 공간/카공'이 나온 원인: 식당에서 '오래 머무르기 좋아요'는 술자리를 뜻하고,
    업종 평균이 0에 가까워 한두 번만 골라도 업종 안 상위가 된다. 식당 데이터에는 카페가 없다.
    → 모델 보정 전에 업종별로 말이 안 되는 태그를 먼저 막는다(허용표).
  - 단체 회식 태그 제안 반영(대화·모임 + 편의).
  - 배달·포장 전문, 공간 대여, 업종 오분류, 프랜차이즈를 따로 표시해 사람이 확인한다.

출력 (사람이 feedback 열을 채운다):
  데이터/검토/store_level/tag_category_allow_v0.csv
  데이터/검토/store_level/store_exclude_candidates_v0.csv
실행: ~/.venvs/maximus/bin/python 분석/build_tag_review_csv.py <1회차 후보.json> <라벨 폴더>
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_label_round import COMBOS, ROOT, area_features, load, store_features  # noqa: E402

OUT = ROOT / "데이터/검토/store_level"
DB = ROOT / "수집/naver-review-crawler/crawler.db"
TAGS = dict(COMBOS, **{"단체 회식": (["대화·모임", "편의"], "여럿이 넓게 앉아 먹고 마시기 좋은 곳")})

MEAT = {"돼지고기 구이/찜", "소고기 구이/찜", "곱창 전골/구이", "닭/오리고기 구이/찜", "족발/보쌈"}
PRICEY = {"횟집", "곱창 전골/구이", "족발/보쌈", "소고기 구이/찜", "해산물 구이/찜", "뷔페", "복 요리 전문",
          "패밀리레스토랑", "파스타/스테이크"}
QUICK = {"김밥/만두/분식", "토스트/샌드위치/샐러드", "버거", "떡/한과", "마라탕/훠궈", "냉면/밀면",
         "일식 면 요리", "일식 카레/돈가스/덮밥", "구내식당"}
NOT_MEAL = {"떡/한과", "구내식당"}


def propose(tag: str, cat: str):
    """제안 (판정, 이유). 판정: 허용 / 검토 / 차단."""
    if tag in ("카공·스터디 모임", "조용한 작업 공간"):
        if cat == "그 외 기타 간이 음식점":
            return "검토", "카페형 간이음식점이 섞여 있을 수 있음"
        return "차단", "식당의 '오래 머무르기'는 술자리 의미. 카페 데이터 들어오면 카페에서만 씀"
    if cat in NOT_MEAL:
        return "차단", "식사 장소로 추천할 업종 아님"
    if tag in ("가성비 혼밥", "혼밥 감성"):
        if cat in PRICEY:
            return "차단", "1인 식사보다 여럿이 먹는 업종"
        if cat in MEAT | {"치킨", "피자"}:
            return "검토", "1인 메뉴가 있는 곳만 해당"
        return "허용", ""
    if tag == "단체 회식":
        if cat in QUICK:
            return "차단", "빨리 먹고 나오는 업종"
        return "허용", ""
    if tag == "데이트·기념일":
        if cat in {"국/탕/찌개류", "김밥/만두/분식", "치킨", "뷔페"}:
            return "검토", "예외적인 가게만 해당(1회차 꾸러기상사처럼)"
        return "허용", ""
    if tag == "감성 모임" and cat in {"김밥/만두/분식", "버거", "토스트/샌드위치/샐러드"}:
        return "검토", "머물며 얘기하는 업종은 아님"
    return "허용", ""


def labels_by(cand_path: Path, label_dir: Path):
    cand = {s["id"]: s for s in json.loads(cand_path.read_text())["stores"]}
    rows = []
    for f in label_dir.glob("*.json"):
        v = json.loads(f.read_text())
        v = v.get("data", v)
        s = cand.get(v["store_id"])
        if s:
            rows += [(s["category"], t, a) for t, a in v["answers"].items() if t != "느좋"]
    return pd.DataFrame(rows, columns=["category", "tag", "ans"])


def brand(name: str) -> str:
    """상호에서 지점명을 뗀 브랜드 키. '교촌치킨 구의역점'→'교촌치킨', '에이셉피자신당점'→'에이셉피자'."""
    s = re.sub(r"\(.*?\)|\s+", lambda m: " " if m.group().isspace() else "", str(name)).strip()
    if " " in s:
        return s.split(" ")[0]
    m = re.match(r"^(.{3,}?)(?:[가-힣0-9]{2,5}점)$", s)
    return m.group(1) if m else s


def brand_counts(stores: pd.Series, master: pd.Series) -> pd.Series:
    """브랜드 키로 시작하는 마스터 상호 수. 2글자 이하 키(사계절·순 같은 흔한 이름)는 프랜차이즈로 보지 않는다."""
    flat = master.str.replace(r"\s+", "", regex=True)
    keys = stores.map(brand)
    cnt = {k: int(flat.str.startswith(k).sum()) if len(k) >= 3 else 1 for k in keys.unique()}
    return keys.map(cnt)


def exclude_flags(d, meta, pct_all, bcount=None):
    """뺄 가게 후보 플래그 행 목록. bcount(같은 상호 수)를 안 주면 프랜차이즈 플래그는 건너뛴다."""
    cat = meta.category_small
    dd = d[d.store_id.isin(meta.index)]
    txt = dd.review_text.fillna("")
    takeout = txt.str.contains(r"포장|배달|테이크아웃").groupby(dd.store_id).mean()
    rental = txt.str.contains(r"대관|파티룸|공간\s?대여|렌탈").groupby(dd.store_id).sum()
    party = dd.chips.map(lambda ch: "파티하기 좋아요" in ch).groupby(dd.store_id).mean()
    meat_chip = dd.chips.map(lambda ch: "고기 질이 좋아요" in ch).groupby(dd.store_id).mean()
    area = area_features(meta)

    flags = []
    for sid in meta.index:
        c, a = cat[sid], area.area_m2.get(sid)
        f = []
        if takeout[sid] >= 0.3 or (takeout[sid] >= 0.2 and pd.notna(a) and a <= 25):
            f.append(("배달·포장 전문 의심", f"포장·배달 언급 리뷰 {takeout[sid]:.0%}, 면적 {a if pd.notna(a) else '-'}㎡"))
        if rental[sid] >= 2 or (rental[sid] >= 1 and party[sid] >= 0.1):
            f.append(("공간 대여 의심", f"대관·파티룸 언급 {int(rental[sid])}건, '파티하기 좋아요' {party[sid]:.0%}"))
        if c not in MEAT and meat_chip[sid] >= 0.4:
            f.append(("업종 오분류 의심(고깃집)", f"'고기 질이 좋아요' {meat_chip[sid]:.0%}"))
        if area.lic_uptae.get(sid) == "식육(숯불구이)" and c not in MEAT:
            f.append(("업종 오분류 의심(인허가 숯불구이)", "인허가 업태 식육(숯불구이)"))
        if area.lic_uptae.get(sid) == "감성주점":
            f.append(("감성주점", "인허가 업태 감성주점(헌팅포차류)"))
        if bcount is not None and bcount[sid] >= 5:
            land = pct_all.loc[sid, "감성·인테리어·뷰"] >= 0.9
            f.append(("프랜차이즈" + (" (랜드마크 지점 후보)" if land else ""),
                      f"같은 상호 {bcount[sid]}곳" + (", 감성·뷰 전체 상위 10%" if land else "")))
        for kind, ev in f:
            flags.append({"store_id": sid, "store_name": meta.at[sid, "store_name"],
                          "naver_name": meta.at[sid, "naver_place_name"], "area_name": meta.at[sid, "area_name"],
                          "category": c, "flag": kind, "evidence": ev,
                          "place_url": f"https://m.place.naver.com/restaurant/{meta.at[sid, 'place_id']}/home",
                          "proposal": "제외" if kind.startswith(("배달", "공간", "감성주점")) else "검토",
                          "feedback": ""})
    return flags


def main(cand_path: Path, label_dir: Path):
    d = load()
    meta, n, pct, pct_all, hit, evid = store_features(d)
    cat = meta.category_small
    lab = labels_by(cand_path, label_dir)

    # ① 업종×태그 허용표
    rows = []
    for t, (ts, desc) in TAGS.items():
        tag_hit = hit[ts].all(axis=1)
        for c, nc in cat.value_counts().items():
            lc = lab[(lab.category == c) & (lab.tag == t)].ans.value_counts()
            verdict, why = propose(t, c)
            rows.append({"tag": t, "tag_desc": desc, "category": c, "n_stores": nc,
                         "n_hit_now": int(tag_hit[cat == c].sum()),
                         "label_yes": int(lc.get("yes", 0)), "label_no": int(lc.get("no", 0)),
                         "proposal": verdict, "reason": why, "feedback": ""})
    allow = pd.DataFrame(rows)

    # ② 뺄 가게 후보
    master = pd.read_sql("select name from master_dining_stores", sqlite3.connect(DB)).name
    ex = pd.DataFrame(exclude_flags(d, meta, pct_all, brand_counts(meta.store_name, master)))

    OUT.mkdir(parents=True, exist_ok=True)
    allow.to_csv(OUT / "tag_category_allow_v0.csv", index=False, encoding="utf-8-sig")
    ex.to_csv(OUT / "store_exclude_candidates_v0.csv", index=False, encoding="utf-8-sig")
    print(allow.groupby(["tag", "proposal"]).n_hit_now.agg(["size", "sum"]).unstack().fillna(0).astype(int).to_string())
    print(ex.flag.value_counts().to_string())
    print(f"점포 {len(meta):,}곳 중 플래그 {ex.store_id.nunique():,}곳 → {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
