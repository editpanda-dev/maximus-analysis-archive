# -*- coding: utf-8 -*-
"""프랜차이즈 판정 v1: 전국 상가(상권)정보의 상호명·지점명으로 본다.

v0(상호 앞부분이 같은 서울 점포 수)은 '사계절'·'자매분식' 같은 흔한 이름을 프랜차이즈로 잡고,
'교촌치킨방이 2호점'처럼 지점명이 붙은 이름은 놓쳤다(2026-11-15 3회차 메모).
v1 규칙: 브랜드(상호명 공백 제거, 또는 "브랜드…점" 꼴 상호의 앞부분) 전국 음식점 수 ≥ MIN_STORES,
  지점명 열이 있거나 상호에 지점이 붙은 비율 ≥ MIN_BRANCH_SHARE, 브랜드 이름 그대로인 점포 ≥ MIN_EXACT.
  흔한 이름(고향식당)은 전국에 많아도 지점명이 거의 없어서 걸러진다.

입력: 데이터/원천/sbiz_store_info_20260630.zip (17개 시도 CSV)
출력: 데이터/가공/store_level/franchise_brands_v1.csv (브랜드별 전국 점포 수·지점명 비율·판정)
      데이터/가공/store_level/store_franchise_v1.csv  (서울 음식점 상가업소번호별 판정)
실행: ~/.venvs/maximus/bin/python 분석/build_franchise_flags.py
"""
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "데이터/원천/sbiz_store_info_20260630.zip"
OUT = ROOT / "데이터/가공/store_level"
MIN_STORES, MIN_BRANCH_SHARE, MIN_EXACT = 5, 0.3, 3
COLS = ["상가업소번호", "상호명", "지점명", "상권업종대분류명", "시군구명", "행정동명"]
# 지명이나 흔한 말로 시작하는 상호('이태원…점', '생고기…점')가 브랜드로 잡히지 않게 뺀다
GENERIC = {"생고기", "우리동네", "한라산", "하루방", "원조", "옛날", "전통", "할매", "할머니", "엄마손", "고향"}


def _name(info):
    try:
        return info.filename.encode("cp437").decode("cp949")
    except UnicodeError:
        return info.filename


def read_food():
    z = zipfile.ZipFile(SRC)
    parts = []
    for info in z.infolist():
        name = _name(info)
        if not name.endswith(".csv"):
            continue
        df = pd.read_csv(z.open(info), usecols=COLS, dtype=str, keep_default_na=False)
        df = df[df.상권업종대분류명 == "음식"]
        df["seoul"] = "서울" in name
        parts.append(df)
    d = pd.concat(parts, ignore_index=True)
    d["brand"] = d.상호명.str.replace(r"\s+|\(.*?\)", "", regex=True)
    return d


def brand_table(d):
    """브랜드 후보별 점포 수. 상호명에 지점이 붙은 경우('교촌치킨신림점')도 앞부분 브랜드로 센다."""
    exact = d.groupby("brand").agg(n_exact=("상가업소번호", "size"),
                                   n_branch_col=("지점명", lambda s: (s.str.strip() != "").sum()))
    # 'X…점' 꼴 상호의 앞부분(3글자 이상)마다 하나씩 센다
    ext = {}
    for name in d.brand[d.brand.str.endswith("점")]:
        for k in range(3, len(name) - 1):
            ext[name[:k]] = ext.get(name[:k], 0) + 1
    b = exact[exact.index.str.len() >= 3].copy()
    b["n_ext"] = b.index.map(ext).fillna(0).astype(int)
    b["n_stores"] = b.n_exact + b.n_ext
    b["branch_share"] = (b.n_branch_col + b.n_ext) / b.n_stores  # 지점명 열이 있거나 상호에 지점이 붙은 비율
    # 브랜드 이름 그대로 쓰는 점포가 3곳 이상이어야 한다('행복한'·'할머니' 같은 앞부분만 겹치는 말 제외)
    places = set(d.시군구명) | set(d.행정동명) | {p[:-1] for p in set(d.행정동명) if p[-1:] == "동"}
    b["franchise"] = ((b.n_stores >= MIN_STORES) & (b.branch_share >= MIN_BRANCH_SHARE) & (b.n_exact >= MIN_EXACT)
                      & ~b.index.isin(GENERIC | places)
                      # 3글자 브랜드('흑돼지'·'플러스')는 지점명 열을 3번 이상 쓴 경우만
                      & ((b.index.str.len() > 3) | (b.n_branch_col >= 3)))
    return b


def match_brand(name, fr: set):
    """상호(공백 제거)가 프랜차이즈 브랜드로 시작하면 가장 긴 브랜드를 돌려준다."""
    for k in range(len(name), 2, -1):
        if name[:k] in fr:
            return name[:k]
    return ""


def main():
    d = read_food()
    b = brand_table(d)
    OUT.mkdir(parents=True, exist_ok=True)
    b.sort_values("n_stores", ascending=False).to_csv(OUT / "franchise_brands_v1.csv", encoding="utf-8-sig")
    fr = set(b.index[b.franchise])
    s = d[d.seoul].copy()
    s["brand"] = s.brand.map(lambda x: match_brand(x, fr))
    s["franchise"] = s.brand != ""
    s = s.merge(b[["n_stores", "branch_share"]], left_on="brand", right_index=True, how="left")
    s = s.assign(store_id="semas:" + s.상가업소번호)[["store_id", "상호명", "지점명", "brand", "n_stores",
                                                     "branch_share", "franchise"]]
    s.to_csv(OUT / "store_franchise_v1.csv", index=False, encoding="utf-8-sig")
    print(f"전국 음식점 {len(d):,} · 브랜드 {len(b):,} → 프랜차이즈 브랜드 {int(b.franchise.sum()):,}")
    print(f"서울 음식점 {len(s):,} 중 프랜차이즈 {int(s.franchise.sum()):,} ({s.franchise.mean():.1%})")


if __name__ == "__main__":
    main()
