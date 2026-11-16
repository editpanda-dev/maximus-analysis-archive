#!/usr/bin/env python3
"""SERP-v1 검증 5종 (2026-11-16).

A. PATH-v0 상위는 의외성 추천으로 쓸 만한가: 상위 10곳의 관련성 R·의외성 U·실제 유입 순위·거리
B. 리뷰 신호 대조: 의외성 상위 상권의 네이버 별점·리뷰 수가 같은 규모 상권보다 높은가
C. 목적별 U: 점포 태그 비율로 식사 하위 목적(느좋·데이트·가성비 혼밥·단체 회식)마다 목록을 나누면 달라지는가
D. 시간 검증: 앞 4달(2025-12~2026-03)로 고른 '덜 가는 곳'이 뒤 4달에 평균 회귀 이상으로 따라잡는가
E. 대학생 하위집단: 다른 대학 학생 모형이 예상한 것보다 우리 캠퍼스 학생이 덜 가는 곳

입력: 데이터/가공/elastic_net/serendipity_ranking_v1.csv, serp_v1_monthly_gap.csv,
      데이터/가공/naver_reviews/dining_store_by_area.csv, area_dining_review_summary.csv,
      데이터/가공/store_level/store_tags_v3.csv, 데이터/가공/od_eval/students/202512-202607/ddm_campus_student_residual.csv
출력: 데이터/가공/elastic_net/validation/*.csv, 요약은 표준 출력
실행: ~/.venvs/maximus/bin/python 분석/serp_v1_validation.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "데이터/가공"
OUT = G / "elastic_net/validation"
TOP = 10
TAGS = ["느좋", "감성 모임", "데이트·기념일", "가성비 혼밥", "단체 회식"]
MIN_TAGGED = 5  # 태그 비율을 믿을 최소 판정 점포 수
CAMPUS = {"회기동": "경희대", "이문1동": "한국외대", "전농2동": "서울시립대 쪽", "휘경2동": "삼육보건대 쪽"}


def load_rank() -> pd.DataFrame:
    r = pd.read_csv(G / "elastic_net/serendipity_ranking_v1.csv")
    r["act_rank"] = r.groupby(["purpose", "age_grp"]).act.rank(ascending=False)
    r["dist_rank"] = r.groupby(["purpose", "age_grp"]).dist_km.rank()
    return r


def pick(r: pd.DataFrame, how: str) -> pd.DataFrame:
    if how == "SERP-v1":
        return r[r.assigned & (r.mmr_rank <= TOP)]
    col, asc = {"PATH-v0": ("path_pct", False), "거리순": ("dist_km", True), "실제 인기순": ("act", False)}[how]
    return r.sort_values(col, ascending=asc).groupby(["purpose", "age_grp"]).head(TOP)


def part_a(r: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for how in ["PATH-v0", "SERP-v1", "거리순", "실제 인기순"]:
        p = pick(r, how)
        p = p[p.age_grp == "전체"]
        rows.append({
            "목록": how,
            "관련성R_중앙": p.relevance.median(),
            "R_0.6이상_비율": (p.relevance >= 0.6).mean(),
            "동료대비_실제배율_중앙": p.peer_ratio.median(),
            "실제유입순위_중앙": p.act_rank.median(),
            "대중교통분_중앙": p.transit_min.median(),
            "30분이내_비율": (p.transit_min <= 30).mean(),
            "관성(이미많이감)_비율": p.inertia.mean(),
            "관광특구_비율": p.area_type_name.eq("관광특구").mean(),
        })
    a = pd.DataFrame(rows)
    path = pick(r, "PATH-v0")
    path[(path.age_grp == "전체")][["purpose", "area_name", "path_pct", "relevance", "peer_ratio", "act_rank", "transit_min", "inertia"]].to_csv(
        OUT / "a_path_top10_detail.csv", index=False, encoding="utf-8-sig")
    return a


def area_reviews() -> pd.DataFrame:
    s = pd.read_csv(G / "naver_reviews/dining_store_by_area.csv")
    s = s[s.usable & s.naver_review_total.notna()]
    a = s.groupby("area_code").agg(
        stores=("store_id", "size"),
        score_med=("naver_review_score", "median"),
        reviews_med=("naver_review_total", "median"),
    )
    summ = pd.read_csv(G / "naver_reviews/area_dining_review_summary.csv").set_index("area_code")
    a = a.join(summ[["food_stores", "crawl_coverage"]])
    a = a[(a.stores >= 10) & (a.crawl_coverage >= 0.8)].copy()
    # 같은 규모 대비: log(식사 점포 수)로 회귀한 잔차
    for col in ["score_med", "reviews_med"]:
        y = np.log1p(a[col]) if col == "reviews_med" else a[col]
        ok = y.notna()
        b = np.polyfit(np.log(a.loc[ok, "food_stores"]), y[ok], 1)
        a[col + "_resid"] = y - np.polyval(b, np.log(a.food_stores))
    return a


def part_b(r: pd.DataFrame, ar: pd.DataFrame) -> pd.DataFrame:
    base = r[(r.age_grp == "전체") & (r.purpose == "식사")].set_index("area_code").join(ar, how="inner")
    rows = []
    groups = {
        "SERP-v1 상위(5목적 합집합)": set(pick(r, "SERP-v1").query("age_grp=='전체'").area_code),
        "PATH-v0 상위(5목적 합집합)": set(pick(r, "PATH-v0").query("age_grp=='전체'").area_code),
        "추천 후보 전체(eligible)": set(r[r.eligible].area_code),
        "전체 상권": set(base.index),
    }
    for k, codes in groups.items():
        g = base[base.index.isin(codes)]
        rows.append({"집단": k, "상권수(리뷰충분)": len(g),
                     "별점 규모보정 잔차 평균": g.score_med_resid.mean(),
                     "리뷰수 규모보정 잔차 평균(log)": g.reviews_med_resid.mean(),
                     "별점 중앙값": g.score_med.median(), "점포당 리뷰 수 중앙": g.reviews_med.median()})
    b = pd.DataFrame(rows)
    el = base[base.eligible]
    rho_s = stats.spearmanr(el.unexpectedness, el.score_med_resid, nan_policy="omit")
    rho_r = stats.spearmanr(el.unexpectedness, el.reviews_med_resid, nan_policy="omit")
    serp = base[base.index.isin(groups["SERP-v1 상위(5목적 합집합)"])]
    rest = el[~el.index.isin(serp.index)]
    mw = stats.mannwhitneyu(serp.score_med_resid.dropna(), rest.score_med_resid.dropna())
    mw2 = stats.mannwhitneyu(serp.reviews_med_resid.dropna(), rest.reviews_med_resid.dropna())
    b.attrs["note"] = (f"후보 안에서 U와 별점 잔차 Spearman {rho_s.statistic:.3f} (p {rho_s.pvalue:.3f}), "
                       f"U와 리뷰 수 잔차 {rho_r.statistic:.3f} (p {rho_r.pvalue:.3f}). "
                       f"SERP 상위 vs 나머지 후보: 별점 잔차 p {mw.pvalue:.3f}, 리뷰 수 잔차 p {mw2.pvalue:.3f}")
    serp[["area_name", "unexpectedness", "stores", "score_med", "score_med_resid", "reviews_med", "reviews_med_resid"]].sort_values(
        "score_med_resid", ascending=False).to_csv(OUT / "b_serp_top_reviews.csv", encoding="utf-8-sig")
    return b


def part_c(r: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = pd.read_csv(G / "store_level/store_tags_v3.csv", keep_default_na=False)
    t = t[t.excluded.astype(str) != "True"]
    for tag in TAGS[1:]:
        t[tag] = t.tags.str.split("|").apply(lambda x, tag=tag: tag in x)
    t["느좋"] = t["느좋"].astype(str) == "True"
    m = pd.read_csv(G / "naver_reviews/dining_store_by_area.csv", usecols=["area_code", "store_id"]).drop_duplicates()
    sa = m.merge(t[["store_id", *TAGS]], on="store_id")
    share = sa.groupby("area_code").agg(n=("store_id", "size"), **{k: (k, "mean") for k in TAGS})
    share = share[share.n >= MIN_TAGGED]
    base = r[(r.purpose == "식사") & (r.age_grp == "전체") & r.eligible].set_index("area_code").join(share, how="inner")
    lists = {"식사(기존)": base.sort_values("serendipity_score", ascending=False).head(TOP)}
    for tag in TAGS:
        fit = base[tag].rank(pct=True)
        s = base.serendipity_score * fit * (base[tag] > 0)
        lists[tag] = base.assign(sub_score=s).sort_values("sub_score", ascending=False).head(TOP)
    names = list(lists)
    ov = pd.DataFrame([[len(set(lists[a].index) & set(lists[b].index)) for b in names] for a in names], index=names, columns=names)
    detail = pd.concat({k: v[["area_name", "relevance", "unexpectedness", "n", *TAGS]] for k, v in lists.items()})
    detail.to_csv(OUT / "c_dining_subpurpose_top10.csv", encoding="utf-8-sig")
    ov.attrs["note"] = f"태그 판정 점포 {MIN_TAGGED}곳 이상 + 식사 추천 후보 상권 {len(base)}곳 기준"
    return ov, detail


def part_d() -> pd.DataFrame:
    g = pd.read_csv(G / "elastic_net/serp_v1_monthly_gap.csv")
    r = pd.read_csv(G / "elastic_net/serendipity_ranking_v1.csv")
    rows = []
    for (purpose, age), d in g.groupby(["purpose", "age_grp"]):
        d = d.assign(half=np.where(d.month.astype(str) <= "202603", "앞", "뒤"))
        h = d.groupby(["area_code", "half"])[["act", "exp"]].sum().unstack()
        lr = np.log((h["act"] + 5) / (h["exp"] + 5))
        lr = lr.dropna()
        el = r[(r.purpose == purpose) & (r.age_grp == age) & r.eligible & (r.relevance >= 0.6) & ~r.inertia].area_code
        lr = lr[lr.index.isin(el)]
        if len(lr) < 40:
            continue
        slope, icpt = np.polyfit(lr["앞"], lr["뒤"], 1)
        pred = icpt + slope * lr["앞"]
        low = lr["앞"].rank() <= TOP  # 앞 4달 기준 가장 덜 간 10곳
        gain = (lr["뒤"] - pred)[low]
        rows.append({"목적": purpose, "연령": age, "후보": len(lr), "앞→뒤 상관": np.corrcoef(lr["앞"], lr["뒤"])[0, 1],
                     "회귀 기울기": slope, "선정 10곳 앞 배율": np.exp(lr["앞"][low].mean()),
                     "뒤 실제 배율": np.exp(lr["뒤"][low].mean()), "뒤 예상 배율(평균회귀)": np.exp(pred[low].mean()),
                     "예상 대비 추가 상승(log)": gain.mean(), "t": gain.mean() / (lr["뒤"] - pred).std() * np.sqrt(len(gain))})
    return pd.DataFrame(rows)


def part_e() -> pd.DataFrame:
    s = pd.read_csv(G / "od_eval/students/202512-202607/ddm_campus_student_residual.csv")
    rk = pd.read_csv(G / "elastic_net/serendipity_ranking_v1.csv")
    inertia = set(rk[rk.inertia].area_code)
    s = s[(s.pred_n >= 20) & ~s.area_code.isin(inertia) & (s.primary_district_name != "동대문구")]
    s["ratio"] = np.exp(s.resid)
    out = (s.sort_values("resid").groupby("campus").head(TOP)
             [["campus", "area_name", "primary_district_name", "dist_km", "pred_n", "y", "ratio"]])
    out["학교"] = out.campus.map(CAMPUS)
    out.to_csv(OUT / "e_campus_under_visited.csv", index=False, encoding="utf-8-sig")
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    r = load_rank()
    print("\n[A] 목록별 성격 (연령 전체, 5목적 × 상위 10)\n", part_a(r).round(3).to_string(index=False))
    b = part_b(r, area_reviews())
    print("\n[B] 리뷰 신호 (식사 점포 리뷰, 규모 보정 잔차)\n", b.round(3).to_string(index=False), "\n", b.attrs["note"])
    ov, _ = part_c(r)
    print("\n[C] 식사 하위 목적별 상위 10 겹침\n", ov.to_string(), "\n", ov.attrs["note"])
    d = part_d()
    d.to_csv(OUT / "d_time_holdout.csv", index=False, encoding="utf-8-sig")
    print("\n[D] 시간 검증 (앞 4달로 고른 덜 가는 10곳의 뒤 4달)\n", d.round(3).to_string(index=False))
    e = part_e()
    print("\n[E] 다른 대학생 대비 우리 학생이 덜 가는 곳 (동대문구 밖, 예상 20명+)\n", e.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
