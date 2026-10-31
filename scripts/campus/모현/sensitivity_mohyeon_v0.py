"""모현 v0 임의 기준값 민감도.

    상권: DBSCAN 반경(60·100·150m) × 최소 점포(10·20·30·50) × 대기(없음·배차 절반) → 30분 안 상권 수·점포 수,
          식사 점수 1~3위가 기준안(100m·30·대기 없음) 1~3위와 같은 곳(300m 안)인지
    노포: 인허가 기준연도(2000·2005·2010) × 상호 유사도(0.5·0.6·0.7) → 노포 수
실행: ~/.venvs/maximus/bin/python 분석/모현/sensitivity_mohyeon_v0.py
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_mohyeon_scorecard_v0 as sc  # noqa: E402
import static_transit_reach as st  # noqa: E402

OUT = sc.OUT


def top3(f: pd.DataFrame, all_stores) -> pd.DataFrame:
    share = all_stores.subtype.isin(sc.PURPOSES["food"][1]).sum() / len(all_stores)
    s = sc.score_unit(f, "food", sc.PURPOSES["food"][1], share)
    return f.join(s).nlargest(3, "food_score")[["dest_lat", "dest_lon"]]


def same_place(a: pd.DataFrame, b: pd.DataFrame, m: float = 300) -> int:
    d = np.hypot((a.dest_lat.values[:, None] - b.dest_lat.values) * 111_000,
                 (a.dest_lon.values[:, None] - b.dest_lon.values) * 88_600)
    return int((d.min(1) <= m).sum())


def main() -> None:
    raw = pd.read_csv(sc.RAW / "sbiz_stores_within20km_globalcampus_202606.csv", dtype=str)
    raw[["경도", "위도"]] = raw[["경도", "위도"]].astype(float)
    raw["dist"] = raw.dist_km_from_globalcampus.astype(float)
    raw["subtype"] = raw["상권업종소분류코드"].map(sc.CODE_TO_SUBTYPE)
    all_stores = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw["경도"], raw["위도"]), crs=4326).to_crs(5179)
    near = all_stores[all_stores.dist <= sc.MAX_STRAIGHT_KM]

    net = st.BusNetwork()
    best, _ = st.calibrate(net, pd.read_csv(OUT / "mohyeon_reach_calibration_v0.csv").drop(columns="est_min"))
    stop = {w: net.stop_times(best["local_kmh"], best["express_kmh"], best["transfer_min"], wait=w) for w in (False, True)}

    rows, base = [], None
    for eps, mn, wait in itertools.product((100, 60, 150), (30, 10, 20, 50), (False, True)):
        sc.CLUSTER_EPS_M, sc.MIN_CLUSTER_STORES = eps, mn
        c, member = sc.build_clusters(near)
        c["reach_min"] = net.to_points(stop[wait], c.dest_lat, c.dest_lon)
        r = c[c.reach_min <= sc.REACH_MIN]
        f = sc.count_units(r, member[member.cluster.isin(r.cluster)], all_stores)
        t = top3(f, all_stores) if len(f) >= 3 else None
        if base is None:
            base = t
        rows.append({"eps_m": eps, "min_stores": mn, "wait": "배차 절반" if wait else "없음", "clusters_30min": len(r),
                     "stores_30min": int(r.stores.sum()), "top3_same_as_base": same_place(t, base) if t is not None else None})
        print(rows[-1])
    pd.DataFrame(rows).to_csv(OUT / "mohyeon_sensitivity_clusters_v0.csv", index=False, encoding="utf-8-sig")

    # 노포 기준
    import build_mohyeon_hidden_stores_v0 as hs  # noqa: E402
    lic = pd.read_csv(sc.RAW / "인허가_일반음식점/general_restaurants_cheoin_gwangju_20261029.csv", dtype=str)
    lic = lic[lic.SALS_STTS_CD == "01"].copy()
    lic["year"] = pd.to_numeric(lic.LCPMT_YMD.str[:4], errors="coerce")
    geo = pd.read_csv(sc.RAW / "인허가_일반음식점/kakao_geocode_missing_coords_20261029.csv", dtype={"MNG_NO": str}).dropna()
    has = lic.CRD_INFO_X.notna()
    a = gpd.GeoDataFrame(lic[has], geometry=gpd.points_from_xy(lic[has].CRD_INFO_X.astype(float), lic[has].CRD_INFO_Y.astype(float)), crs=5174).to_crs(5179)
    m = lic[~has].merge(geo, on="MNG_NO")
    b = gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(m.kakao_lon, m.kakao_lat), crs=4326).to_crs(5179)
    lic = pd.concat([a, b[a.columns]], ignore_index=True)
    lic["key"] = lic.BPLC_NM.map(hs.norm)
    lic4326 = lic.to_crs(4326)
    lic["reach_min"] = net.to_points(stop[False], lic4326.geometry.y, lic4326.geometry.x)
    stores = near[(near["상권업종대분류코드"] == "I2")].copy()
    stores["key"] = stores["상호명"].map(hs.norm)
    buf = lic[lic.reach_min <= sc.REACH_MIN].assign(lic_id=lambda d: d.index)
    buf["geometry"] = buf.buffer(hs.NAME_MATCH_M)
    cand = gpd.sjoin(stores[["key", "geometry"]], buf[["lic_id", "key", "year", "geometry"]], predicate="within", lsuffix="s", rsuffix="l")
    ratio = [hs.SequenceMatcher(None, x, y).ratio() if not (x in y or y in x) else 1.0 for x, y in zip(cand.key_s, cand.key_l)]
    cand["ratio"] = ratio
    nrows = []
    for year, sim in itertools.product((2000, 2005, 2010), (0.5, 0.6, 0.7)):
        hit = cand[(cand.year <= year) & (cand.ratio >= sim)]
        nrows.append({"nopo_year": year, "similarity": sim, "nopo_stores": hit.index.nunique(),
                      "old_licenses_30min": int((buf.year <= year).sum())})
    pd.DataFrame(nrows).to_csv(OUT / "mohyeon_sensitivity_nopo_v0.csv", index=False, encoding="utf-8-sig")
    print(pd.DataFrame(nrows).to_string(index=False))


if __name__ == "__main__":
    main()
