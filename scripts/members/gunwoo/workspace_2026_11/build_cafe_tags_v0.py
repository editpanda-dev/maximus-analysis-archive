# -*- coding: utf-8 -*-
"""카페 태그 v0 (2026-11-23): 네이버 키워드 칩 비율 규칙. 라벨이 없어 식사 v1과 같은 규칙 단계다.

점수: 태그마다 칩 묶음이 있고, 리뷰 한 건이 묶음 칩을 하나라도 고르면 1.
  점포 비율을 카페 평균 쪽으로 당긴다: (선택 수 + M × 카페 평균) ÷ (칩 달린 리뷰 수 + M), M = 5.
  그 값의 카페 전체 백분위가 점수(score_<태그>).
해당: 점수 ≥ 0.8 이고 묶음 칩 선택 2건 이상, 칩 달린 리뷰 8건 이상.
  테이크아웃 전문(네이버 업종 '테이크아웃커피')은 머무는 태그(카공·작업, 대화·모임, 감성·사진, 조용·차분)에서 뺀다.
  체인: 상호(공백 제거)가 전국 프랜차이즈 브랜드로 시작하거나, 같은 기본 상호가 카페 안에 5곳 이상이면 chain=True.
  태그는 그대로 주고 표시만 한다.
출력: 데이터/가공/store_level/cafe_tags_v0.csv
실행: ~/.venvs/maximus/bin/python 분석/build_cafe_tags_v0.py
다음: 라벨 페이지로 태그별 30곳씩 확인 → 로지스틱(식사 v3 방식)으로 옮긴다. 방문 정보(혼자·친구·데이트)가 모이면 피처로 넣는다.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "데이터/가공/naver_reviews_cafe/cafe_reviews_clean.csv"
OUT = ROOT / "데이터/가공/store_level/cafe_tags_v0.csv"
BRANDS = ROOT / "데이터/가공/store_level/franchise_brands_v1.csv"  # 전국 프랜차이즈 판정(분석/build_franchise_flags.py)
GENERIC = {"브레드", "더카페", "카페다"}  # 앞부분만 맞춰서 개인 카페까지 잡히는 일반 단어 (11-23 확인)
M, HI, MIN_HIT, MIN_N, CHAIN_N = 5, 0.8, 2, 8, 5
TAGS = {
    "카공·작업": ["집중하기 좋아요", "오래 머무르기 좋아요", "좌석이 편해요"],
    "대화·모임": ["대화하기 좋아요", "단체모임 하기 좋아요", "매장이 넓어요"],
    "감성·사진": ["인테리어가 멋져요", "사진이 잘 나와요", "음악이 좋아요", "컨셉이 독특해요"],
    "조용·차분": ["차분한 분위기예요", "아늑해요"],
    "뷰·야외": ["뷰가 좋아요", "야외공간이 멋져요"],
    "디저트·베이커리": ["디저트가 맛있어요", "빵이 맛있어요"],
    "커피·차 맛집": ["커피가 맛있어요", "차가 맛있어요"],
    "가성비": ["가성비가 좋아요", "가격이 합리적이에요"],
    "반려동물 동반": ["반려동물과 가기 좋아요"],
    "아이 동반": ["아이와 가기 좋아요"],
}
STAY = ["카공·작업", "대화·모임", "감성·사진", "조용·차분"]
BRANCH = re.compile(r"\s*[가-힣A-Za-z\d]+(?:점|호점|본점|직영점)$")


def base_name(n):
    s = re.sub(r"\(.*?\)", " ", str(n)).strip()
    return re.sub(r"\s+", "", BRANCH.sub("", s) or s).lower()


def main():
    d = pd.read_csv(SRC, dtype=str, keep_default_na=False, encoding="utf-8-sig",
                    usecols=["store_id", "store_name", "area_name", "naver_place_name", "naver_category",
                             "naver_review_total", "keywords", "extra_tags"])
    d["chips"] = [{x.strip() for x in f"{a}, {b}".split(",") if x.strip()} for a, b in zip(d.keywords, d.extra_tags)]
    d = d[d.chips.str.len() > 0]
    meta = d.drop_duplicates("store_id").set_index("store_id")[["store_name", "area_name", "naver_place_name",
                                                                "naver_category", "naver_review_total"]]
    n = d.groupby("store_id").size().reindex(meta.index)
    hits = pd.DataFrame({t: d.chips.map(lambda c, ks=set(ks): bool(c & ks)).groupby(d.store_id).sum()
                         for t, ks in TAGS.items()}).reindex(meta.index)
    mu = hits.sum() / n.sum()
    rate = (hits + M * mu) / (n.values[:, None] + M)
    score = rate.rank(pct=True)

    ok = (n >= MIN_N).values[:, None] & (score >= HI).values & (hits >= MIN_HIT).values
    ok = pd.DataFrame(ok, index=meta.index, columns=list(TAGS))
    takeout = meta.naver_category.str.contains("테이크아웃", na=False)
    ok.loc[takeout, STAY] = False
    base = meta.store_name.map(base_name)
    brands = pd.read_csv(BRANDS, encoding="utf-8-sig")
    brands = sorted({b for b in brands[brands.franchise].brand.astype(str) if len(b) >= 2} - GENERIC, key=len, reverse=True)
    pat = re.compile("^(?:" + "|".join(map(re.escape, brands)) + ")")
    flat = meta.store_name.astype(str).str.replace(r"\s+", "", regex=True)
    meta["chain"] = (base.map(base.value_counts()) >= CHAIN_N) | flat.map(lambda s: bool(pat.match(s)))
    meta["takeout"] = takeout
    meta["n_chip_reviews"] = n
    meta["tags"] = ok.apply(lambda r: "|".join(t for t in TAGS if r[t]), axis=1)
    out = meta.join(score.round(3).add_prefix("score_"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, encoding="utf-8-sig")
    print(f"카페 {len(out):,}곳 (칩 리뷰 {MIN_N}건 이상 {int((n >= MIN_N).sum()):,}곳) · 체인 {int(meta.chain.sum()):,} · 테이크아웃 {int(takeout.sum()):,}")
    print(ok.sum().rename("해당").to_frame().assign(체인_비율=lambda x: [ok[t][meta.chain].sum() / max(ok[t].sum(), 1) for t in TAGS]).round(2).to_string())
    for t in ["카공·작업", "감성·사진", "대화·모임"]:
        top = out[ok[t] & ~meta.chain].sort_values("score_" + t, ascending=False).head(5)
        print(t, "→", ", ".join(f"{r.store_name}({r.area_name})" for r in top.itertuples()))


if __name__ == "__main__":
    main()
