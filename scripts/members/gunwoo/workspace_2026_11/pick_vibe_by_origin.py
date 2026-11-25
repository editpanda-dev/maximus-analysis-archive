# -*- coding: utf-8 -*-
"""출발동 기준 의외성 상권 top N과 상권별 '숨은 느좋' 가게 (2026-11-24).

상권: SERP-v1 순위 파일(목적·연령)에서 추천 자격(eligible) 있고, 출발동에서 대중교통 MAX_MIN분 안인 곳을 mmr_rank 순으로.
가게: v5 느좋 = True, 제외 아님, 프랜차이즈 아님, 네이버 방문자 리뷰 수 ≤ REVIEW_CAP(유명한 곳은 '숨은'이 아님).
  REVIEW_CAP 기본 1,000 = 서울 식사 점포 리뷰 수 상위 약 15% 경계(중앙값 277).
실행: ~/.venvs/maximus/bin/python 분석/pick_vibe_by_origin.py [순위파일] [출발동코드] [목적] [연령]
  예) ... serendipity_ranking_v1_2_1106089.csv 1106089 식사 20대
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "데이터/가공/elastic_net"
TOP_N, MAX_MIN, REVIEW_CAP, SHOW = 5, 30, 1000, 6


def main(rank_file="serendipity_ranking_v1_2.csv", origin="1106089", purpose="식사", age="20대"):
    s = pd.read_csv(EN / rank_file, dtype={"area_code": str})
    tt = pd.read_csv(ROOT / "데이터/가공/od_eval/transit_time_origin_area.csv", dtype={"origin": str, "area_code": str})
    tt = tt[tt.origin == origin].set_index("area_code").transit_min
    x = s[(s.purpose == purpose) & (s.age_grp == age)].copy()
    x["min_from_origin"] = x.area_code.map(tt)
    top = x[x.eligible & (x.min_from_origin <= MAX_MIN)].sort_values("mmr_rank").head(TOP_N)

    sa = pd.read_csv(ROOT / "데이터/가공/naver_reviews/dining_store_by_area.csv", dtype={"area_code": str})
    tg = pd.read_csv(ROOT / "데이터/가공/store_level/store_tags_v5.csv", keep_default_na=False, index_col=0)
    print(f"# {rank_file} · 출발 {origin} · {purpose}·{age} · {MAX_MIN}분 안 · 가게 리뷰 ≤ {REVIEW_CAP:,} · 프랜차이즈 제외")
    for i, a in enumerate(top.itertuples(), 1):
        u = sa[(sa.area_code == a.area_code) & (sa.usable.astype(str) == "True")].set_index("store_id")
        t = tg.reindex(u.index).dropna(subset=["store_name"])
        t = t.assign(rev=u.naver_review_total.reindex(t.index), name=u.naver_place_name.reindex(t.index))
        vibe = t[(t["느좋"].astype(str) == "True") & (t.excluded.astype(str) != "True")]
        keep = vibe[(vibe.franchise.astype(str) != "True") & (vibe.rev <= REVIEW_CAP)].sort_values("p_느좋", ascending=False)
        print(f"\n## {i}. {a.area_name} ({a.primary_district_name}) · {a.min_from_origin:.0f}분 · 예상의 {a.peer_ratio:.2f}배 · "
              f"{a.under_months}/8달 덜 감 · 느좋 {len(vibe)}곳 중 숨은 느좋 {len(keep)}곳 (태그 대상 {len(t)}/{len(u)})")
        for r in keep.head(SHOW).itertuples():
            print(f"- {r.name or r.store_name} | {r.category} | 리뷰 {int(r.rev):,} | 느좋 {r.p_느좋:.2f} | "
                  f"{str(r.rep_menu)[:30] or '-'} | {r.tags or '-'}")


if __name__ == "__main__":
    main(*sys.argv[1:])
