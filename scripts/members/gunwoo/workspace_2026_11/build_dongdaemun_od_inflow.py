#!/usr/bin/env python3
"""서울 생활이동(열린데이터광장, 행정동 OD) → 동대문구발 상권 유입.

원천: 데이터/원천/seoul_living_migration/living_migration_admdong_202607.zip
  열: 대상연월, 요일, 도착시간, 출발/도착 행정동 코드(통계용 7자리), 성별, 나이, 이동유형, 평균 이동 시간, 이동인구(합)
  이동유형: 출발·도착 체류지 유형 2글자. H 야간상주지(집), W 주간상주지(직장·학교), E 기타.
  이동인구 3명 이하는 '*'로 가려져 있다.

만드는 것
  - 출발: 동대문구 14개 동(코드 11060xx)
  - 비일상 이동 = 도착이 E(기타 장소)인 이동(HE·WE·EE). 출근·등교(→W)와 귀가(→H)는 뺀다.
  - '*' 처리: 기본은 2명(1~3의 가운데). 민감도로 0명·3명도 같이 계산.
  - 도착 동 → 상권: 기존 build_living_movement_features.py와 같은 겹침 비율 배분
    (행정동 유입 × 상권 겹침 면적 / 그 동에 걸친 상권 겹침 면적 합)

실행: ~/.venvs/maximus/bin/python 분석/build_dongdaemun_od_inflow.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
SRC = HERE / "데이터/원천/seoul_living_migration"
REPO = HERE / "maximus-analysis-archive"
OUT = HERE / "데이터/가공/elastic_net"
DDM_PREFIX = "11060"
COLS = ["출발 행정동 코드", "도착 행정동 코드", "이동유형", "이동인구(합)"]


def load_ddm_od() -> pd.DataFrame:
    z = zipfile.ZipFile(SRC / "living_migration_admdong_202607.zip")
    parts = []
    for info in z.infolist():
        for ch in pd.read_csv(z.open(info), encoding="cp949", dtype=str, usecols=COLS, chunksize=2_000_000):
            ch = ch[ch["출발 행정동 코드"].str.startswith(DDM_PREFIX)]
            masked = ch["이동인구(합)"].eq("*")
            ch = ch.assign(cnt=pd.to_numeric(ch["이동인구(합)"], errors="coerce").fillna(0.0), masked=masked.astype(int),
                           dest_type=ch["이동유형"].str[1])
            parts.append(ch.groupby(["도착 행정동 코드", "dest_type"], as_index=False)[["cnt", "masked"]].sum())
        print("read", info.filename.encode("cp437", "ignore").decode("cp949", "ignore") or info.filename)
    od = pd.concat(parts).groupby(["도착 행정동 코드", "dest_type"], as_index=False)[["cnt", "masked"]].sum()
    return od.rename(columns={"도착 행정동 코드": "stat_code"})


def stat_to_admin() -> pd.DataFrame:
    """통계용 7자리 코드 → 행안부 8자리(겹침 파일) 이름으로 연결."""
    code = pd.read_excel(SRC / "서울생활이동데이터_행정동코드_20210907.xlsx", dtype=str)
    code["district"] = code["full_name"].str.split().str[1]
    code = code.rename(columns={"읍면동": "stat_code", "name": "admin_name"})[["stat_code", "district", "admin_name"]]
    ov = pd.read_csv(REPO / "data/processed/commercial_area_accessibility/commercial_area_dong_overlap.csv",
                     dtype={"admin_code": str, "area_code": str})
    adm = ov[["admin_code", "admin_name", "district_name"]].drop_duplicates().rename(columns={"district_name": "district"})
    norm = lambda s: s.str.replace("·", ".", regex=False).str.replace(" ", "", regex=False)
    code["k"], adm["k"] = norm(code["district"] + code["admin_name"]), norm(adm["district"] + adm["admin_name"])
    # 2021 코드표 이후 개편된 동: 새 동으로 넘긴다. 둘로 나뉜 동은 겹침 파일의 동 면적 비율로 나눈다.
    # 가양2동은 대응 동을 확인하지 못해 미연결로 둔다.
    alias = {"동대문구용신동": ["동대문구용두동", "동대문구신설동"], "강동구상일동": ["강동구상일제1동"],
             "강남구일원2동": ["강남구개포3동"]}
    size = ov.groupby("admin_code")["overlap_m2"].sum()
    adm["size"] = adm["admin_code"].map(size)
    xw = code.merge(adm[["k", "admin_code", "size"]], on="k", how="left").assign(weight=1.0)
    extra = []
    for old, news in alias.items():
        tgt = adm[adm["k"].isin(news)]
        base = code[code["k"] == old]
        for _, t in tgt.iterrows():
            extra.append(base.assign(admin_code=t["admin_code"], weight=t["size"] / tgt["size"].sum()))
    xw = pd.concat([xw[~xw["k"].isin(alias)], *extra], ignore_index=True)
    return xw[["stat_code", "district", "admin_name", "admin_code", "weight"]], ov


def main() -> None:
    od = load_ddm_od()
    xwalk, ov = stat_to_admin()
    od = od.merge(xwalk[["stat_code", "admin_code", "admin_name", "weight"]], on="stat_code", how="left")
    od["weight"] = od["weight"].fillna(1.0)
    od[["cnt", "masked"]] = od[["cnt", "masked"]].mul(od["weight"], axis=0)
    seoul = od[od["stat_code"].str.startswith("11")]
    unmatched = seoul[seoul["admin_code"].isna()]
    print(f"서울 도착 동 {seoul.stat_code.nunique()}개 중 행안부 코드 미연결 {unmatched.stat_code.nunique()}개, "
          f"유입 비중 {unmatched.cnt.sum() / seoul.cnt.sum():.3%}")

    rows = []
    for name, fill in [("mask2", 2.0), ("mask0", 0.0), ("mask3", 3.0)]:
        d = seoul.assign(v=seoul["cnt"] + seoul["masked"] * fill)
        dong = d.pivot_table(index="admin_code", columns="dest_type", values="v", aggfunc="sum", fill_value=0)
        dong = dong.reindex(columns=["E", "H", "W"], fill_value=0).add_prefix(f"{name}_")
        rows.append(dong)
    dong = pd.concat(rows, axis=1).reset_index()

    ov = ov[["area_code", "admin_code", "overlap_share"]].copy()
    ov["w"] = ov["overlap_share"] / ov.groupby("admin_code")["overlap_share"].transform("sum")
    j = ov.merge(dong, on="admin_code", how="inner")
    val = [c for c in dong.columns if c != "admin_code"]
    j[val] = j[val].mul(j["w"], axis=0)
    area = j.groupby("area_code", as_index=False)[val].sum()
    area = area.rename(columns={"mask2_E": "ddm_nonroutine", "mask2_W": "ddm_to_work", "mask2_H": "ddm_to_home"})
    OUT.mkdir(parents=True, exist_ok=True)
    area.to_csv(OUT / "dongdaemun_od_inflow_202607.csv", index=False, encoding="utf-8-sig")
    masked_share = seoul.loc[seoul.dest_type == "E", "masked"].sum() * 2 / (
        seoul.loc[seoul.dest_type == "E", "cnt"].sum() + seoul.loc[seoul.dest_type == "E", "masked"].sum() * 2)
    print(f"상권 {len(area)}곳, 동대문구발 비일상(→E) 합 {area.ddm_nonroutine.sum():,.0f}, '*' 대입분 비중 {masked_share:.1%}")
    print("마스크 0 vs 3 순위상관:", round(area["mask0_E"].corr(area["mask3_E"], method="spearman"), 3))


if __name__ == "__main__":
    main()
