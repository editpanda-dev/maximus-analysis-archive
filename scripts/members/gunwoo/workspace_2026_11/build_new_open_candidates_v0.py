# -*- coding: utf-8 -*-
"""2025년 이후 개업한 식사 가게 = '새로 생긴 힙한 곳' 후보 v0 (2026-11-24).

개업일: 지방행정 인허가(일반·휴게음식점 등) 개업일. 상호가 정확히 맞거나 관리번호로 붙은 매칭만 쓰고, 폐업은 뺀다.
느좋 확률: 칩 리뷰 10건 이상이면 v5(store_tags_v5), 칩이 적고 글 리뷰 3건 이상이면 본문 Jev 모형(store_vibe_textonly_v0).
  둘 다 없으면 비워 둔다(리뷰가 거의 없는 곳: 방문 정보·메뉴판·페이지 정보로 따로 봐야 함).
프랜차이즈: 전국 상호·지점명 판정(store_franchise_v1).
출력: 데이터/가공/store_level/new_open_candidates_v0.csv
실행: ~/.venvs/maximus/bin/python 분석/build_new_open_candidates_v0.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "데이터/가공/store_level"
NR = ROOT / "데이터/가공/naver_reviews"
SINCE = "2025-01-01"


def main():
    lic = pd.read_csv(STORE / "store_localdata_match.csv", dtype=str)
    lic = lic[lic.match_type.isin(["exact", "id"]) & (lic.lic_state != "폐업")].copy()
    lic["store_id"] = lic.store_id.where(~lic.store_id.str.startswith("MA"), "semas:" + lic.store_id)
    lic["open_date"] = pd.to_datetime(lic.lic_open_date, errors="coerce")
    new = lic[lic.open_date >= SINCE].drop_duplicates("store_id").set_index("store_id")[["open_date", "lic_uptae", "area_m2"]]

    sa = pd.read_csv(NR / "dining_store_by_area.csv", dtype={"area_code": str})
    areas = sa.groupby("store_id").area_name.apply(lambda s: ", ".join(s.unique()[:2]))
    st = sa.drop_duplicates("store_id").set_index("store_id")
    out = new.join(st[["store_name", "naver_place_name", "subcategory", "review_status", "usable", "naver_review_total"]], how="inner")
    out["areas"] = areas.reindex(out.index)

    v5 = pd.read_csv(STORE / "store_tags_v5.csv", keep_default_na=False, index_col=0)
    tx = pd.read_csv(STORE / "store_vibe_textonly_v0.csv", index_col=0)
    fr = pd.read_csv(STORE / "store_franchise_v1.csv", dtype=str).set_index("store_id").franchise.eq("True")
    out["p_느좋"] = v5.p_느좋.reindex(out.index)
    out["vibe_source"] = out.p_느좋.notna().map({True: "v5", False: ""})
    fill = out.p_느좋.isna() & out.index.isin(tx.index)
    out.loc[fill, "p_느좋"] = tx.p_느좋.reindex(out.index)[fill]
    out.loc[fill, "vibe_source"] = "본문 Jev"
    out["느좋_v5"] = v5["느좋"].reindex(out.index).astype(str).eq("True")
    out["tags"] = v5.tags.reindex(out.index).fillna("")
    out["franchise"] = fr.reindex(out.index).fillna(False)
    out = out.sort_values("p_느좋", ascending=False)
    out.to_csv(STORE / "new_open_candidates_v0.csv", encoding="utf-8-sig")

    print(f"{SINCE} 이후 개업(영업 중) 식사 가게 {len(out):,}곳 · 네이버 매칭 {int(out.usable.astype(str).eq('True').sum()):,}곳")
    print("느좋 확률 출처:", out.vibe_source.replace("", "없음").value_counts().to_dict())
    hit = out[(out.p_느좋 >= 0.6) & ~out.franchise]
    print(f"느좋 확률 0.6 이상 · 프랜차이즈 아님: {len(hit):,}곳 (리뷰 1,000 이하 {int((hit.naver_review_total <= 1000).sum()):,}곳)")
    for r in hit[hit.naver_review_total <= 1000].head(12).itertuples():
        print(f"- {r.naver_place_name or r.store_name} | {r.subcategory} | {r.areas} | 개업 {r.open_date:%Y-%m} | "
              f"리뷰 {int(r.naver_review_total):,} | 느좋 {r.p_느좋:.2f} ({r.vibe_source})")


if __name__ == "__main__":
    main()
