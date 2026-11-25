# -*- coding: utf-8 -*-
"""4개 분기 숨은 활력·리듬 패널을 만든다 (panel.pkl, stable_hid.pkl)."""
import io, zipfile
import numpy as np, pandas as pd

R = "/Users/gw-Kim/post/maximus-analysis-archive/"
S = "/Users/gw-Kim/post/프로젝트/DAT/프로젝트_막시무스/데이터/캐시/openapi_분기패널/"
def z(p):
    a = zipfile.ZipFile(R + p)
    return pd.read_csv(io.BytesIO(a.read(a.namelist()[0])), encoding="cp949", low_memory=False)

c = pd.read_csv(R + "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv", dtype={"area_code": str}).set_index("area_code")
keep = c.index[c.area_type_name != "관광특구"]
st = z("data/raw/commercial_area/commercial_store_2025.zip"); st = st[st.stor_co > 0]
st["ac"] = st.trdar_cd.astype(str).str.zfill(7)
sa = z("data/raw/commercial_area/commercial_sales_2025.zip"); sa["ac"] = sa["상권_코드"].astype(str).str.zfill(7)

rows = []
for q in [20251, 20252, 20253, 20254]:
    s1 = st[st.stdr_yyqu_cd == q]; s2 = sa[sa["기준_년분기_코드"] == q]
    m = s1.merge(s2, left_on=["ac", "svc_induty_cd_nm"], right_on=["ac", "서비스_업종_코드_명"])
    m["tps"] = m["당월_매출_건수"] / m.stor_co
    m = m.join(m.groupby(["svc_induty_cd_nm", "trdar_se_cd_nm"]).tps.median().rename("bench"), on=["svc_induty_cd_nm", "trdar_se_cd_nm"])
    m["exp"] = m.bench * m.stor_co
    g = m[m.ac.isin(keep)].groupby("ac").agg(obs=("당월_매출_건수", "sum"), exp=("exp", "sum"), disc=("stor_co", "sum"), cells=("stor_co", "size"))
    g["coverage"] = g.disc / s1[s1.ac.isin(keep)].groupby("ac").stor_co.sum().reindex(g.index)
    g = g[(g.disc >= 20) & (g.cells >= 3)]
    g["rel"] = (g.obs / g.exp) / (g.obs / g.exp).median()
    a = s2[s2.ac.isin(keep)].groupby("ac")
    amt = a["당월_매출_금액"].sum()
    rh = pd.DataFrame({
        "wk": a["주말_매출_금액"].sum() / amt,
        "eve": (a["시간대_17~21_매출_금액"].sum() + a["시간대_21~24_매출_금액"].sum()) / amt,
        "young": (a["연령대_10_매출_금액"].sum() + a["연령대_20_매출_금액"].sum()) / amt,
    }).join(c.area_type_name)
    for col in ["wk", "eve", "young"]:
        rh[col + "_z"] = rh.groupby("area_type_name")[col].transform(lambda s: (s - s.mean()) / s.std())
    out = g[["rel", "coverage"]].join(rh[["wk", "eve", "young", "wk_z", "eve_z", "young_z"]], how="outer")
    out.index.name = "ac"; out["q"] = q
    rows.append(out.reset_index())
panel = pd.concat(rows)
panel.to_pickle(S + "panel.pkl")
covw = panel[panel.coverage >= 0.6].pivot_table(index="ac", columns="q", values="rel")
hit = (covw >= 1.8).sum(axis=1)
stable = covw[(hit >= 3) & (covw[20254] >= 1.8)].copy()
stable["mean_rel"] = covw.loc[stable.index].mean(axis=1)
stable = stable.join(c[["area_name", "area_type_name", "primary_district_name"]])
stable.to_pickle(S + "stable_hid.pkl")
print("panel rows", len(panel), "stable hidden", len(stable))
