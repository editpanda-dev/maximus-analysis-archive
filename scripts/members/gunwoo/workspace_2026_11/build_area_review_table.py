# -*- coding: utf-8 -*-
"""상권 단위 네이버 리뷰 집계표 v1 (2026-11-23, 식사). 숨은 상권 A·B·의외성(한별님 문서)에 붙여 쓰는 용도.

한 행 = 서울 공식 상권 하나. 가게는 상권-점포 매핑(dining_store_by_area.csv) 기준이라 한 가게가 여러 상권에 들어갈 수 있다.
열
  food_stores            상권 안 식사 점포 수(소상공인 기준)
  usable_stores          네이버 매칭이 맞고 리뷰를 쓸 수 있는 점포 수
  review_total_sum       네이버 방문자 리뷰 수 합 (인지도 대리값. 매출보다 '알려진 정도'에 가깝다)
  review_total_median    점포당 네이버 리뷰 수 중앙값
  store_pop_top3_pct     상권 안 리뷰 수 상위 3개 가게 평균의 서울 상권 백분위 = '가게 인기도(리뷰)'.
                         주의: 상권 이름이 얼마나 알려졌는지(인지도)가 아니다. 경리단길·해방촌은 이름은 유명하지만
                         가게 리뷰는 중간(0.66·0.69)으로 나온다(11-23 확인). 인지도는 검색량·설문으로 재야 한다
  low_review_share       점포 리뷰 수가 서울 식사 점포 중앙값 이하인 점포 비율
  revisit_share          수집 리뷰 중 재방문(2번째 방문 이상) 비율의 점포 평균
  tagged_stores          태그 모형(v5) 대상 점포 수 (칩 달린 리뷰가 충분한 곳)
  n_<태그>, share_<태그>  태그 해당 점포 수와 tagged_stores 대비 비율 (느좋·감성 모임·데이트·기념일·가성비 혼밥·단체 회식·야장·야외석·이색 체험)
  hidden_stores          숨은 가게 수 = 리뷰 수 서울 하위 50% 이고 재방문 비율 서울 상위 25%(수집 리뷰 10건 이상)
  low_review_vibe_stores 느좋인데 리뷰 수 서울 하위 50%인 점포 수 ('숨은'이 아니라 '리뷰가 적은' 느좋 가게)
  hidden_share           hidden_stores ÷ usable_stores
  low_review_vibe_share  low_review_vibe_stores ÷ tagged_stores
  ddm_act, ddm_exp, ddm_peer_ratio, ddm_inertia
                         SERP-v1(식사, 전체 연령): 동대문구민 실제 유입, 동료 출발지 기준 예상 유입, 실제÷예상, 늘 가던 곳 여부.
                         peer_ratio < 1 이면 동대문구민이 비슷한 조건보다 덜 간다
입력: 데이터/가공/naver_reviews/{dining_store_by_area,dining_reviews_clean}.csv, 데이터/가공/store_level/store_tags_v5_1.csv
출력: 데이터/가공/area_level/area_review_table_v1.csv
실행: ~/.venvs/maximus/bin/python 분석/build_area_review_table.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NR = ROOT / "데이터/가공/naver_reviews"
SERP = ROOT / "데이터/가공/elastic_net/serendipity_ranking_v1_2.csv"
TAGS_CSV = ROOT / "데이터/가공/store_level/store_tags_v5_1.csv"
OUT = ROOT / "데이터/가공/area_level/area_review_table_v1.csv"
TAGS = ["감성 모임", "데이트·기념일", "가성비 혼밥", "단체 회식", "야장·야외석", "이색 체험"]


def main():
    sa = pd.read_csv(NR / "dining_store_by_area.csv", dtype={"area_code": str})
    rv = pd.read_csv(NR / "dining_reviews_clean.csv", usecols=["store_id", "visit_count"], encoding="utf-8-sig")
    tg = pd.read_csv(TAGS_CSV, keep_default_na=False, index_col=0)

    # 점포 단위
    st = sa.drop_duplicates("store_id").set_index("store_id")
    st = st[st.usable.astype(str) == "True"]
    v = pd.to_numeric(rv.visit_count, errors="coerce")
    g = rv.assign(re=(v >= 2).astype(float).where(v.notna())).groupby("store_id")
    st["revisit"] = g.re.mean().reindex(st.index)
    st["collected"] = g.size().reindex(st.index)
    med = st.naver_review_total.median()
    st["low_review"] = st.naver_review_total <= med
    rq = st.revisit[st.collected >= 10].quantile(0.75)
    st["hidden"] = st.low_review & (st.collected >= 10) & (st.revisit >= rq)
    tg = tg.reindex(st.index)
    st["tagged"] = tg.store_name.notna()
    st["t_느좋"] = tg["느좋"].astype(str) == "True"
    for t in TAGS:
        st["t_" + t] = tg.tags.fillna("").str.split("|").apply(lambda x, t=t: t in x)
    st["low_review_vibe"] = st["t_느좋"] & st.low_review

    # 상권 단위
    m = sa[["area_code", "area_name", "store_id"]].merge(st.drop(columns=["area_code", "area_name"]), on="store_id")
    a = m.groupby(["area_code", "area_name"])
    out = pd.DataFrame({
        "usable_stores": a.size(),
        "review_total_sum": a.naver_review_total.sum(),
        "review_total_median": a.naver_review_total.median(),
        "low_review_share": a.low_review.mean(),
        "revisit_share": a.revisit.mean(),
        "tagged_stores": a.tagged.sum(),
        "hidden_stores": a.hidden.sum(),
        "low_review_vibe_stores": a.low_review_vibe.sum(),
        "top3": a.naver_review_total.apply(lambda s: s.nlargest(3).mean()),
    })
    for t in ["느좋"] + TAGS:
        out["n_" + t] = a["t_" + t].sum()
        out["share_" + t] = (out["n_" + t] / out.tagged_stores).where(out.tagged_stores > 0)
    food = sa.groupby(["area_code", "area_name"]).size().rename("food_stores")
    out = food.to_frame().join(out, how="left").fillna({"usable_stores": 0})
    out.insert(4, "store_pop_top3_pct", out.pop("top3").rank(pct=True))
    # 개수는 큰 상권일수록 커지므로 비율도 둔다 (A·B 비교에는 비율을 쓴다)
    out["hidden_share"] = (out.hidden_stores / out.usable_stores).where(out.usable_stores > 0)
    out["low_review_vibe_share"] = (out.low_review_vibe_stores / out.tagged_stores).where(out.tagged_stores > 0)
    sp = pd.read_csv(SERP, dtype={"area_code": str})
    sp = sp[(sp.purpose == "식사") & (sp.age_grp == "전체")].set_index("area_code")[["act", "exp", "peer_ratio", "inertia"]]
    out = out.reset_index().merge(sp.add_prefix("ddm_"), left_on="area_code", right_index=True, how="left") \
             .set_index(["area_code", "area_name"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.round(4).reset_index().to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"상권 {len(out)}곳 · 서울 식사 점포 리뷰 수 중앙값 {med:.0f} · 재방문 상위 25% 기준 {rq:.2f}")
    print(f"숨은 가게 {int(st.hidden.sum()):,}곳 · 리뷰 적은 느좋 {int(st.low_review_vibe.sum()):,}곳 · SERP 붙은 상권 {int(out.ddm_act.notna().sum())} → {OUT}")


if __name__ == "__main__":
    main()
