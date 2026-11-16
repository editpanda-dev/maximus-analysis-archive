#!/usr/bin/env python3
"""대학생 이동 근사: '대학이 있는 동'에서 '주간 상주지(W, 학생에겐 학교)'를 떠나 '기타 장소(E)'로 간 20대(20~29세).

원천: 서울 생활이동 OD 2026-06 패널(build_seoul_od_panel.py), 서울시 집객시설 행정동(대학교_수, 2026 2분기).
캠퍼스 동: 대학교_수 ≥ 10인 동 + 동대문구에서 대학교_수 ≥ 4인 동(휘경2동 삼육보건대).
  (대학교_수는 대학 건물 수에 가까운 값이라 문턱으로 큰 캠퍼스만 고른다)

만드는 것
  1) 학생 신호 점검: 캠퍼스 동 vs 다른 동의 'W→E 이동 중 20대 비중'
  2) 동대문구 캠퍼스(경희대 회기동·외대 이문1동·시립대 전농2동·삼육보건대 휘경2동) 학생 행선지 상위
  3) 다른 대학 학생 모형(EN, 동대문 밖 캠퍼스로 학습) vs 실제
     - 평가: 동대문 캠퍼스 학생 행선지를 거리순·PATH·다른 대학생 인기순보다 잘 맞히나
     - 잔차: '다른 대학 학생이라면 갈 법한데 우리 학교 학생은 덜 가는 곳'(음수) / '우리 학교만 가는 곳'(양수)

실행: ~/.venvs/maximus/bin/python 분석/student_flows.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_destination_ranking import ndcg_recall  # noqa: E402
from eval_generalization import HERE, MASK_FILL, PANEL, REPO, fit_en, load_common, long_table  # noqa: E402

MONTH = "202606"
OUT = PANEL / "students"


def campus_dongs(xw: pd.DataFrame) -> pd.DataFrame:
    f = pd.read_csv(REPO / "data/raw/seoul_attracting_facilities_dong.csv", encoding="cp949", dtype={"행정동_코드": str})
    f = f[f["기준_년분기_코드"] == f["기준_년분기_코드"].max()]
    f = f[(f["대학교_수"] >= 10) | (f["행정동_코드"].str.startswith("11230") & (f["대학교_수"] >= 4))]
    m = f[["행정동_코드", "행정동_코드_명", "대학교_수"]].merge(xw, left_on="행정동_코드", right_on="admin_code")
    return m.drop_duplicates("stat_code")[["stat_code", "district", "admin_name", "대학교_수"]]


def student_labels(panel: pd.DataFrame, alloc: pd.DataFrame, codes, origins) -> pd.DataFrame:
    d = panel[panel.origin.isin(origins) & (panel.otype == "W") & (panel.age20 == 1) & (panel.origin != panel.dest)].copy()
    d["v"] = d["cnt"] + MASK_FILL * d["masked"]
    d = d.groupby(["origin", "dest"], as_index=False)["v"].sum().merge(alloc, left_on="dest", right_on="stat_code")
    d["y"] = d["v"] * d["w"]
    d = d[d.area_code.isin(codes)].groupby(["origin", "area_code"], as_index=False)["y"].sum()
    return d.assign(slot="오후", age_grp="20대")  # long_table/features 형식 맞춤(슬롯은 전 시간 합)


def main() -> None:
    global OUT
    # 인자: 합칠 달들(예: 202603 202604 202605 202606). 없으면 6월만.
    months = sys.argv[1:] or [MONTH]
    tag = months[0] if len(months) == 1 else f"{months[0]}-{months[-1]}"
    OUT = PANEL / "students" / tag
    OUT.mkdir(parents=True, exist_ok=True)
    xw, alloc, origin_xy, area, static, path = load_common()
    codes = static.index.to_numpy()
    names = area.set_index("area_code")[["area_name", "primary_district_name"]]
    panel = pd.concat([pd.read_csv(PANEL / f"seoul_od_E_{m}.csv.gz", dtype={"origin": str, "dest": str}) for m in months])
    panel = panel.groupby(["origin", "dest", "otype", "slot", "age20"], as_index=False)[["cnt", "masked"]].sum()
    print("달:", months)
    camp = campus_dongs(xw)
    camp = camp[camp.stat_code.isin(origin_xy.index)]
    ddm = camp[camp.district == "동대문구"]
    print("캠퍼스 동", len(camp), "| 동대문구:", ddm.admin_name.tolist())

    # 1) 학생 신호 점검
    w = panel[panel.otype == "W"].assign(v=lambda d: d.cnt + MASK_FILL * d.masked)
    share = w.groupby("origin").apply(lambda g: g.loc[g.age20 == 1, "v"].sum() / g["v"].sum())
    is_c = share.index.isin(camp.stat_code)
    print(f"W→E 중 20대 비중: 캠퍼스 동 중앙값 {share[is_c].median():.1%} vs 그 밖 {share[~is_c].median():.1%}")
    print(pd.DataFrame({"동": ddm.admin_name.values, "20대 비중": share.reindex(ddm.stat_code).round(3).values}).to_string(index=False))

    # 2) 동대문 캠퍼스 학생 행선지
    lab = student_labels(panel, alloc, codes, camp.stat_code)
    rows = []
    for _, c in ddm.iterrows():
        g = lab[lab.origin == c.stat_code].nlargest(10, "y").join(names, on="area_code")
        rows.append(g.assign(campus=c.admin_name, share=g.y / lab.loc[lab.origin == c.stat_code, "y"].sum()))
    top = pd.concat(rows)
    top.to_csv(OUT / "ddm_campus_student_top10.csv", index=False, encoding="utf-8-sig")
    for cam, g in top.groupby("campus", sort=False):
        print(f"\n[{cam}] 학생 행선지 상위:", ", ".join(f"{n}({s:.0%})" for n, s in zip(g.area_name, g.share)))

    # 3) 다른 대학 학생 모형
    tr_o = [o for o in camp.stat_code if o not in set(ddm.stat_code)]
    tr = long_table(lab, tr_o, codes, origin_xy, area, alloc)
    te = long_table(lab, ddm.stat_code.tolist(), codes, origin_xy, area, alloc)
    pop = lab[lab.origin.isin(tr_o)].groupby("area_code")["y"].sum()
    from eval_generalization import features
    has_tt = "transit_min" in te

    def fit_predict(tt: bool):
        Xtr, Xte = features(tr, static, path, pop, tt), features(te, static, path, pop, tt)
        keep = [c for c in Xtr.columns if Xtr[c].std() > 0]  # 슬롯·연령 상수 열 제거
        mm = fit_en(Xtr[keep], np.log1p(tr.y.to_numpy()), tr.origin.to_numpy())
        return mm, keep, mm.predict(Xte[keep])

    m, keep, te["pred_base"] = fit_predict(False)
    te["pred"] = te["pred_base"]
    if has_tt:  # 잔차는 교통 변수판 기준(철도 직결 효과를 뺀 '의외성')
        m, keep, te["pred"] = fit_predict(True)
    ev = []
    for o, g in te.groupby("origin"):
        y = g.y.to_numpy()
        cands = {"거리순": -g.dist_km, "인기순(PATH 식사·카페 평균)": g.area_code.map((path["식사"] + path["카페"]) / 2),
                 "다른 대학생 인기순": g.area_code.map(pop).fillna(0), "EN(다른 대학 학습)": g.pred_base}
        if has_tt:
            cands |= {"교통시간순": -g.transit_min, "EN+교통(다른 대학 학습)": g.pred}
        for name, sc in cands.items():
            n, r = ndcg_recall(y, np.asarray(sc, float))
            ev.append({"campus": origin_xy.at[o, "name"], "model": name, "ndcg10": n, "recall10": r})
    ev = pd.DataFrame(ev)
    print("\n동대문 캠퍼스 학생 행선지 맞히기(NDCG@10):")
    print(ev.pivot(index="model", columns="campus", values="ndcg10").round(3).assign(평균=lambda d: d.mean(axis=1).round(3)).to_string())
    coef = pd.Series(m[-1].coef_, index=keep)
    print("\nEN 계수 상위:", coef[coef.abs().sort_values(ascending=False).index].head(10).round(3).to_dict())

    # 잔차: 실제·예측 모두 동 안 학생 총량으로 나눈 비중 기준으로 비교 (log 비중 차이)
    te["pred_n"] = np.expm1(te.pred).clip(lower=0)
    te["act_share"] = te.y / te.groupby("origin").y.transform("sum")
    te["pred_share"] = te.pred_n / te.groupby("origin").pred_n.transform("sum")
    te["resid"] = np.log((te.act_share + 1e-4) / (te.pred_share + 1e-4))
    te = te.join(names, on="area_code").assign(campus=te.origin.map(origin_xy["name"]))
    te.to_csv(OUT / "ddm_campus_student_residual.csv", index=False, encoding="utf-8-sig")
    for cam, g in te.groupby("campus"):
        under = g[(g.pred_share >= g.pred_share.quantile(0.95)) & (g.dist_km <= 8)].nsmallest(6, "resid")
        over = g[g.act_share >= g.act_share.quantile(0.95)].nlargest(6, "resid")
        tmin = under["transit_min"] if has_tt else under["dist_km"] * np.nan
        print(f"\n[{cam}] 다른 대학생이면 갈 법한데 덜 감:", ", ".join(f"{n}({d:.1f}km·{t:.0f}분, 실제/예상 {np.exp(r):.2f}배)" for n, d, t, r in zip(under.area_name, under.dist_km, tmin, under.resid)))
        print(f"[{cam}] 우리 학생만 많이 감:", ", ".join(f"{n}({np.exp(r):.1f}배)" for n, r in zip(over.area_name, over.resid)))


if __name__ == "__main__":
    main()
