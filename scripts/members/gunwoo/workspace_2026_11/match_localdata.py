# -*- coding: utf-8 -*-
"""상가정보 점포(master_dining_stores) ↔ 서울시 음식점 인허가 매칭 → 면적·업태 붙이기.

매칭: 점포 좌표 반경 RADIUS m 안 인허가 업소 중 상호 유사도가 가장 높은 것.
      상호 유사도 = max(포함 여부, 글자 2-gram 자카드). MIN_SIM 이상만 채택.
      같은 건물 주소(도로명 앞부분)가 같으면 거리 제한을 FAR_RADIUS까지 늘린다.
인허가는 영업/정상 + 2026-06 이후 폐업(상가정보 기준월 뒤 폐업 의심)만 후보로 쓴다.

입력: 수집/naver-review-crawler/crawler.db (master_dining_stores),
      데이터/원천/seoul_openapi/localdata_*.csv (분석/download_localdata.py)
출력: 데이터/가공/store_level/store_localdata_match.csv (로컬 전용)

실행: ~/.venvs/maximus/bin/python 분석/match_localdata.py
"""
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "수집/naver-review-crawler/crawler.db"
SRC = ROOT / "데이터/원천/seoul_openapi"
OUT = ROOT / "데이터/가공/store_level/store_localdata_match.csv"
RADIUS, FAR_RADIUS, MIN_SIM = 60.0, 250.0, 0.5
CLOSED_AFTER = "20260601"

_strip = re.compile(r"\(.*?\)|[^0-9a-z가-힣]")
_branch = re.compile(r"(본점|직영점|[가-힣0-9]{1,8}점)$")


def norm(s: str) -> str:
    s = _strip.sub("", str(s).lower())
    t = _branch.sub("", s)
    return t if len(t) >= 2 else s


def sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    ga, gb = {a[i:i + 2] for i in range(len(a) - 1)}, {b[i:i + 2] for i in range(len(b) - 1)}
    return len(ga & gb) / max(1, len(ga | gb))


def road_key(addr: str) -> str:
    """도로명 + 건물번호까지 ('서울특별시 용산구 한강대로 32' → '한강대로32')."""
    m = re.search(r"([가-힣0-9]+(?:로|길))\s*([0-9]+(?:-[0-9]+)?)", str(addr))
    return f"{m.group(1)}{m.group(2)}" if m else ""


def load_license():
    df = pd.concat([pd.read_csv(SRC / f"{n}.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
                    .assign(kind=k) for n, k in [("localdata_general_restaurant", "일반"),
                                                  ("localdata_rest_restaurant", "휴게")]])
    alive = df.TRDSTATENM.eq("영업/정상")
    late_close = df.TRDSTATENM.eq("폐업") & (df.DCBYMD.str.replace("-", "").str[:8] >= CLOSED_AFTER)
    df = df[alive | late_close].copy()
    df["x"], df["y"] = pd.to_numeric(df.X, errors="coerce"), pd.to_numeric(df.Y, errors="coerce")
    df = df.dropna(subset=["x", "y"]).reset_index(drop=True)
    df["area_m2"] = pd.to_numeric(df.FACILTOTSCP, errors="coerce")
    df["nname"] = df.BPLCNM.map(norm)
    df["rkey"] = df.RDNWHLADDR.map(road_key)
    return df


def main():
    stores = pd.read_sql("select store_id, name, branch, address, category, area_name, lat, lon "
                         "from master_dining_stores", sqlite3.connect(DB))
    lic = load_license()
    tf = Transformer.from_crs("EPSG:4326", "EPSG:5174", always_xy=True)
    sx, sy = tf.transform(stores.lon.values, stores.lat.values)
    tree = cKDTree(np.c_[lic.x, lic.y])
    by_rkey = lic.groupby("rkey").indices
    by_mgtno = {g: j for j, g in enumerate(lic.MGTNO)}
    rows = []
    for i, st in enumerate(stores.itertuples()):
        nm = norm(f"{st.name}{st.branch or ''}")
        nm0 = norm(st.name)
        cand = set(tree.query_ball_point([sx[i], sy[i]], FAR_RADIUS))
        rk = road_key(st.address)
        same_bldg = set(by_rkey.get(rk, [])) if rk else set()
        best = None
        j0 = by_mgtno.get(st.store_id[1:]) if st.store_id.startswith("L") else None
        if j0 is not None:  # 인허가에서 온 점포(L+관리번호)는 번호로 바로 붙인다
            best = ((1.0, True, 0.0), j0, float(np.hypot(lic.x[j0] - sx[i], lic.y[j0] - sy[i])), True)
        for j in ([] if best else cand | same_bldg):
            dist = float(np.hypot(lic.x[j] - sx[i], lic.y[j] - sy[i]))
            bldg = j in same_bldg
            if dist > RADIUS and not bldg:
                continue
            s = max(sim(nm, lic.nname[j]), sim(nm0, lic.nname[j]))
            key = (s, bldg, -dist)
            if s >= MIN_SIM and (best is None or key > best[0]):
                best = (key, j, dist, bldg)
        rec = {"store_id": st.store_id}
        if best:
            (s, bldg, _), j, dist, _ = best
            L = lic.iloc[j]
            rec.update(mgtno=L.MGTNO, lic_name=L.BPLCNM, lic_kind=L.kind, lic_uptae=L.UPTAENM,
                       lic_state=L.TRDSTATENM, lic_close_date=L.DCBYMD, lic_open_date=L.APVPERMYMD,
                       area_m2=L.area_m2 if L.area_m2 > 5 else np.nan,  # 5㎡ 이하는 입력 오류로 본다
                       name_sim=round(s, 2), dist_m=round(dist, 1), same_building=bldg,
                       match_type="id" if j == j0 else ("exact" if s == 1 else "fuzzy"))
        rows.append(rec)
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    m = out.mgtno.notna()
    print(f"점포 {len(out):,} → 매칭 {m.sum():,} ({m.mean():.1%}), "
          f"매칭 후 폐업 {(out.lic_state == '폐업').sum():,}, 면적 있음 {(out.area_m2 > 0).sum():,} → {OUT}")


if __name__ == "__main__":
    main()
