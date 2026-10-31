"""모현(한국외대 글로벌캠퍼스) 30분 상권 스코어카드 v0.

동대문 food_shopping_v1(Purpose Score v2) 규칙을 경기 데이터에 맞게 옮긴다.

    상권 단위  = 서울 공식 상권이 없으므로 SBIZ 점포 점을 DBSCAN(100m)으로 묶은 군집(30점포 이상)
    도달      = 캠퍼스(카카오 좌표) → 군집 중심 추정 분(대기 미포함). ODsay가 일일 한도에 걸려 GBIS 노선망 모델
               (static_transit_reach.py)을 10-28 ODsay 실측 13곳에 보정해 쓴다(평균오차 약 3분).
               추정 30분 이내만 점수화하고, 26~34분은 경계로 표시해 ODsay로 다시 확인한다.
    공급 U    = 0.4 P(군집 안 밀도) + 0.3 P(400m 둘레 밀도) + 0.3 P(수축 LQ, 기준=캠퍼스 20km 안 점포 구성)
    소비 V    = 행정동 카드매출(2025-01~06 월평균) / 같은 동 해당 목적 점포 수의 백분위. 목적(식사·쇼핑)만.
               동 단위 값이라 basis=dong_level로 표시.
    점수      = 0.7U + 0.3V (V 있을 때), 아니면 U
    참고 열   = 노포(2005년 이전 인허가·영업 중 일반음식점), 400m 안 정류소 8월 하차, 경로·노선

실행: ~/.venvs/maximus/bin/python 분석/모현/build_mohyeon_scorecard_v0.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import MultiPoint
from sklearn.cluster import DBSCAN

sys.path.insert(0, str(Path(__file__).resolve().parent))
from static_transit_reach import BusNetwork, calibrate  # noqa: E402

ROOT = Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())
RAW = ROOT / "데이터/원천/모현"
OUT = ROOT / "데이터/가공/모현"

CAMPUS = (37.33707, 127.26543)  # 카카오 '한국외국어대학교 글로벌캠퍼스' 좌표
MAX_STRAIGHT_KM = 12  # 30분 대중교통으로 직선 12km 밖은 닿지 않음(10-28 ODsay: 4.7km 능평 33분)
CLUSTER_EPS_M = 100
CLUSTER_MIN_SAMPLES = 15
MIN_CLUSTER_STORES = 30
SPLIT_EXTENT_M = 1500  # 도시부에서 군집이 길게 이어지면 eps를 줄여 한 번 더 나눈다
SPLIT_EPS_M = 60
REACH_MIN = 30
BORDER_MIN = 4  # 보정 평균오차(약 3분)보다 조금 넓게
WALK_BUFFER_M = 400
NOPO_YEAR = 2005

# 동대문 v1과 같은 SBIZ 소분류 → 하위분류. 카페는 참고용 공급 점수만.
SUBTYPES = {
    "M1": ("한식", "food", {f"I201{n:02d}" for n in range(1, 14)} | {"I20199"}),
    "M2": ("중식", "food", {"I20201", "I20202"}),
    "M3": ("일식", "food", {"I20301", "I20302", "I20303", "I20399"}),
    "M4": ("양식·외국식", "food", {"I20401", "I20402", "I20403", "I20499", "I20501", "I20599", "I20601", "I20702"}),
    "M5": ("간편식", "food", {"I21003", "I21004", "I21005", "I21007", "I21099"}),
    "M6": ("치킨", "food", {"I21006"}),
    "SH1": ("패션·뷰티", "shopping", {"G20901", "G20902", "G20903", "G20904", "G20905", "G20907", "G20908", "G20910", "G20911", "G21701", "G21602", "G21503"}),
    "SH2": ("디지털·가전", "shopping", {"G20801", "G20802", "G20803", "G21603"}),
    "SH3": ("홈·리빙", "shopping", {"G21101", "G21201", "G21202", "G20906", "G20909", "G21002"}),
    "SH4": ("취미·문화", "shopping", {"G21304", "G21305", "G21306", "G21203", "G21801", "G21802", "G21901", "G21303"}),
    "SH5": ("장보기·생활", None, {"G20404", "G20405", "G20501", "G20503", "G20504", "G20505", "G20506", "G20508", "G20509", "G21501"}),
    "CF": ("카페·디저트", None, {"I21201", "I21001", "I21002", "I21008"}),
}
PURPOSES = {"food": ("식사", ["M1", "M2", "M3", "M4", "M5", "M6"]), "shopping": ("쇼핑", ["SH1", "SH2", "SH3", "SH4"])}
# 경기 카드매출 중분류 → 목적. 주점·배달·카페·제과·대형휴게소는 식사에서 뺀다.
CARD_CODES = {
    "food": {"Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q10", "Q12", "Q14", "Q15"},
    "shopping": {"D01", "D05", "D06", "D09", "D10", "D14", "D15", "D16"},
}
SUPPLY_WEIGHTS = {"inside_density": 0.4, "walk_density": 0.3, "lq": 0.3}
SUPPLY_SHARE = 0.7
LQ_PRIOR_STORES = 30
DENSITY_SMOOTHING_KM2 = 0.05
SMALL_AREA_STORES = 50
CODE_TO_SUBTYPE = {c: s for s, (_, _, codes) in SUBTYPES.items() for c in codes}


def percentile(values: pd.Series) -> pd.Series:
    return values.rank(pct=True) * 100


def shrunk_lq(group: pd.Series, total: pd.Series, share: float) -> pd.Series:
    return ((group + LQ_PRIOR_STORES * share) / (total + LQ_PRIOR_STORES)) / share


def haversine_km(lat, lon, lat0=CAMPUS[0], lon0=CAMPUS[1]):
    p = np.radians
    a = np.sin(p(lat - lat0) / 2) ** 2 + np.cos(p(lat0)) * np.cos(p(lat)) * np.sin(p(lon - lon0) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


# ---------- 상권 후보 ----------
def build_clusters(stores: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    xy = np.c_[stores.geometry.x, stores.geometry.y]
    labels = DBSCAN(eps=CLUSTER_EPS_M, min_samples=CLUSTER_MIN_SAMPLES).fit_predict(xy)
    next_id = labels.max() + 1
    for lab in np.unique(labels[labels >= 0]):
        idx = np.where(labels == lab)[0]
        ext = np.ptp(xy[idx], axis=0).max()
        if ext > SPLIT_EXTENT_M:
            sub = DBSCAN(eps=SPLIT_EPS_M, min_samples=CLUSTER_MIN_SAMPLES).fit_predict(xy[idx])
            labels[idx] = np.where(sub >= 0, sub + next_id, -1)
            next_id += sub.max() + 1
    stores = stores.assign(cluster=labels)
    sizes = stores[stores.cluster >= 0].cluster.value_counts()
    keep = sizes[sizes >= MIN_CLUSTER_STORES].index
    stores = stores[stores.cluster.isin(keep)]
    rows = []
    for cid, g in stores.groupby("cluster"):
        hull = MultiPoint(list(g.geometry)).convex_hull.buffer(30)  # 점포 줄 하나짜리 군집도 면적을 갖게
        rows.append({
            "cluster": cid, "stores": len(g), "geometry": hull,
            "dest_lat": g["위도"].median(), "dest_lon": g["경도"].median(),
            "sigungu": g["시군구명"].mode().iat[0], "dong_cd": g["행정동코드"].mode().iat[0],
            "dong": g["행정동명"].mode().iat[0], "legal_dong": g["법정동명"].mode().iat[0],
            "main_road": g["도로명"].mode().iat[0] if g["도로명"].notna().any() else "",
            "landmark": g["건물명"][g["건물명"] != "일부"].dropna().mode().iat[0] if (g["건물명"].notna() & (g["건물명"] != "일부")).any() else "",
        })
    return gpd.GeoDataFrame(rows, crs=stores.crs), stores


# ---------- 도달 ----------
def calibration_targets(raw: pd.DataFrame) -> pd.DataFrame:
    """10-28 ODsay 실측(행정동 점포 중앙값 15곳, 지하철 경로 제외)을 보정 기준으로 쓴다."""
    r = raw[raw.dist <= 10]
    g = r.groupby(["시군구명", "행정동명"]).agg(n=("위도", "size"), lat=("위도", "median"), lon=("경도", "median")).reset_index()
    od = pd.read_csv(RAW / "odsay_globalcampus_to_dongs_20261028.csv")
    od = od[~od["경로"].str.contains("지하철")]
    return g[g.n >= 300].merge(od, left_on=["시군구명", "행정동명"], right_on=["시군구", "행정동"]).rename(columns={"최단분": "odsay_min"})


def add_reach(clusters: gpd.GeoDataFrame, raw: pd.DataFrame) -> gpd.GeoDataFrame:
    net = BusNetwork()
    params, check = calibrate(net, calibration_targets(raw))
    check.to_csv(OUT / "mohyeon_reach_calibration_v0.csv", index=False, encoding="utf-8-sig")
    print("calibration", params)
    stop_min = net.stop_times(params["local_kmh"], params["express_kmh"], params["transfer_min"])
    est = net.to_points(stop_min, clusters.dest_lat, clusters.dest_lon)
    band = np.select([est <= REACH_MIN - BORDER_MIN, est <= REACH_MIN, est <= REACH_MIN + BORDER_MIN],
                     ["안쪽", "경계(안)", "경계(밖)"], default="밖")
    return clusters.assign(straight_km=haversine_km(clusters.dest_lat, clusters.dest_lon).values, reach_min=est, reach_band=band)


# ---------- 점수 ----------
def count_units(clusters, stores, all_stores):
    """군집 안·400m 둘레 하위분류 점포 수."""
    inside = stores.groupby(["cluster", "subtype"]).size().unstack(fill_value=0)
    walk_area = clusters[["cluster", "geometry"]].copy()
    walk_area["geometry"] = walk_area.buffer(WALK_BUFFER_M)
    j = gpd.sjoin(all_stores[["subtype", "geometry"]], walk_area, predicate="within")
    walk = j.groupby(["cluster", "subtype"]).size().unstack(fill_value=0)
    f = clusters.set_index("cluster")
    f["area_km2"] = f.area / 1e6
    f["walk_km2"] = walk_area.set_index("cluster").area / 1e6
    f["all_walk"] = j.groupby("cluster").size()
    for s in SUBTYPES:
        f[f"{s}_inside"] = inside.get(s, 0)
        f[f"{s}_walk"] = walk.get(s, 0)
    return f.fillna({c: 0 for c in f.columns if c.endswith(("_inside", "_walk"))})


def score_unit(f, unit, parts, share, demand=None):
    inside = sum(f[f"{s}_inside"] for s in parts)
    walk = sum(f[f"{s}_walk"] for s in parts)
    comp = pd.DataFrame({
        "inside_density": inside / (f.area_km2 + DENSITY_SMOOTHING_KM2),
        "walk_density": walk / f.walk_km2,
        "lq": shrunk_lq(walk, f.all_walk, share),
    })
    p = comp.apply(percentile)
    p.loc[inside == 0, "inside_density"] = 0.0
    p.loc[walk == 0, "walk_density"] = 0.0
    supply = sum(w * p[k] for k, w in SUPPLY_WEIGHTS.items())
    out = pd.DataFrame({f"{unit}_inside": inside, f"{unit}_lq": comp.lq.round(2), f"{unit}_supply": supply.round(1)})
    if demand is not None:
        v = percentile(demand)
        out[f"{unit}_demand"] = v.round(1)
        out[f"{unit}_score"] = np.where(v.notna(), SUPPLY_SHARE * supply + (1 - SUPPLY_SHARE) * v, supply).round(1)
        out[f"{unit}_basis"] = np.where(v.notna(), "dong_level", "supply_only")
    else:
        out[f"{unit}_score"] = supply.round(1)
    return out


def dong_demand(stores_all: pd.DataFrame) -> pd.DataFrame:
    card = pd.read_csv(RAW / "경기_카드매출/card_sales_admdong.csv", dtype=str)
    card = card[card.std_ym.between("202501", "202506")]
    card["admdong_cd"] = card.admdong_cd.str[:8]  # SBIZ 행정동코드는 8자리
    card["sales_amt"] = card.sales_amt.astype(float)
    out = {}
    for purpose, codes in CARD_CODES.items():
        monthly = card[card.mdclass_indutype_cd.isin(codes)].groupby(["admdong_cd", "std_ym"]).sales_amt.sum()
        sales = monthly.groupby("admdong_cd").mean()
        n = stores_all[stores_all.purpose == purpose].groupby("행정동코드").size()
        out[purpose] = (sales / n.reindex(sales.index)).where(n.reindex(sales.index) >= 10)
    return pd.DataFrame(out)


def context_columns(f, clusters):
    """노포·정류소 하차 (점수에는 넣지 않는다)."""
    lic = pd.read_csv(RAW / "인허가_일반음식점/general_restaurants_cheoin_gwangju_20261029.csv", dtype=str)
    lic = lic[lic.SALS_STTS_CD == "01"]
    lic["year"] = pd.to_numeric(lic.LCPMT_YMD.str[:4], errors="coerce")
    has = lic.CRD_INFO_X.notna()
    own = gpd.GeoDataFrame(lic[has], geometry=gpd.points_from_xy(lic[has].CRD_INFO_X.astype(float), lic[has].CRD_INFO_Y.astype(float)), crs=5174).to_crs(5179)
    # 2022년 이후 광주 오포 쪽 인허가는 좌표가 비어 있어 카카오 주소검색 좌표로 채운다
    geo = pd.read_csv(RAW / "인허가_일반음식점/kakao_geocode_missing_coords_20261029.csv", dtype={"MNG_NO": str}).dropna()
    miss = lic[~has].merge(geo, on="MNG_NO")
    filled = gpd.GeoDataFrame(miss, geometry=gpd.points_from_xy(miss.kakao_lon, miss.kakao_lat), crs=4326).to_crs(5179)
    lic = pd.concat([own, filled[own.columns]], ignore_index=True)
    zone = clusters[["cluster", "geometry"]].copy()
    zone["geometry"] = zone.buffer(50)
    j = gpd.sjoin(lic[["year", "BPLC_NM", "geometry"]], zone, predicate="within")
    f["licensed_restaurants"] = j.groupby("cluster").size()
    old = j[j.year <= NOPO_YEAR]
    f["nopo_count"] = old.groupby("cluster").size()
    f["nopo_examples"] = old.sort_values("year").groupby("cluster").apply(
        lambda g: ", ".join(f"{n}({int(y)})" for n, y in zip(g.BPLC_NM.head(3), g.year.head(3))), include_groups=False)
    stops = pd.read_csv(RAW / "경기_정류소승하차/stop_boarding_yongin_gwangju_202608.csv", dtype={"정류소ID": str}).dropna(subset=["x"])
    stops = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops.x, stops.y), crs=4326).to_crs(5179)
    walk = clusters[["cluster", "geometry"]].copy()
    walk["geometry"] = walk.buffer(WALK_BUFFER_M)
    s = gpd.sjoin(stops[["하차", "주말하차", "geometry"]], walk, predicate="within").groupby("cluster")[["하차", "주말하차"]].sum()
    f["stop_alight_202608"] = s["하차"]
    f["stop_weekend_share"] = (s["주말하차"] / s["하차"]).round(2)
    return f


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(RAW / "sbiz_stores_within20km_globalcampus_202606.csv", dtype=str)
    raw[["경도", "위도"]] = raw[["경도", "위도"]].astype(float)
    raw["dist"] = raw.dist_km_from_globalcampus.astype(float)
    raw["subtype"] = raw["상권업종소분류코드"].map(CODE_TO_SUBTYPE)
    raw["purpose"] = raw.subtype.map(lambda s: SUBTYPES[s][1] if isinstance(s, str) else None)
    all_stores = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw["경도"], raw["위도"]), crs=4326).to_crs(5179)
    near = all_stores[all_stores.dist <= MAX_STRAIGHT_KM]

    clusters, member = build_clusters(near)
    print("clusters", len(clusters), "stores in clusters", len(member))
    clusters = add_reach(clusters, raw)
    clusters.drop(columns="geometry").to_csv(OUT / "mohyeon_clusters_reach_v0.csv", index=False, encoding="utf-8-sig")
    reach = clusters[clusters.reach_min <= REACH_MIN].copy()
    print("reachable within", REACH_MIN, "min:", len(reach))

    member = member[member.cluster.isin(reach.cluster)]
    f = count_units(reach, member, all_stores)
    region_total = len(all_stores)
    demand = dong_demand(all_stores)
    parts = []
    for s, (_, _, _) in SUBTYPES.items():
        share = (all_stores.subtype == s).sum() / region_total
        parts.append(score_unit(f, s, [s], share))
    for p, (_, subs) in PURPOSES.items():
        share = all_stores.subtype.isin(subs).sum() / region_total
        parts.append(score_unit(f, p, subs, share, demand[p].reindex(f.dong_cd).set_axis(f.index)))
    card = pd.concat([f[["stores", "sigungu", "dong", "legal_dong", "main_road", "landmark", "dong_cd",
                         "straight_km", "reach_min", "reach_band", "dest_lat", "dest_lon"]]] + parts, axis=1)
    sub_cols = [s for s in SUBTYPES if s not in {"SH5", "CF"}]
    shares = np.c_[[f[f"{s}_inside"] for s in sub_cols]].T
    pr = shares / np.clip(shares.sum(1, keepdims=True), 1, None)
    card["specialty_entropy"] = (-(np.where(pr > 0, pr * np.log(pr), 0)).sum(1)).round(2)
    card["small_area"] = card.stores < SMALL_AREA_STORES
    card["combo_food_shopping"] = card[["food_score", "shopping_score"]].rank(pct=True).mul(100).mean(1).round(1)
    card["combo_ok"] = card[["food_score", "shopping_score"]].rank(pct=True).min(1) >= 0.5
    card = context_columns(card, reach)
    card["reach_min"] = card.reach_min.round(1)
    card["straight_km"] = card.straight_km.round(2)
    card = card.sort_values("food_score", ascending=False)
    card.to_csv(OUT / "mohyeon_scorecard_v0.csv", encoding="utf-8-sig")
    reach.merge(card[["food_score", "shopping_score"]], left_on="cluster", right_index=True).to_crs(4326).to_file(
        OUT / "mohyeon_scorecard_v0.geojson", driver="GeoJSON")
    print("saved", len(card))


if __name__ == "__main__":
    main()
