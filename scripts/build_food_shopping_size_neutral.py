"""Build size-neutral food and shopping signals for the 786 reachable areas.

PATH-v0 counts purpose stores inside each official polygon, so large polygons
win almost every purpose (score vs. total stores rho 0.62-0.76). This script
measures supply on a common walking footprint instead: every polygon is
buffered by 400m and stores are counted from the point-level SBIZ store file.
Sales stay at the official-area level, but are turned into per-store
productivity and only used where disclosed cells cover most purpose stores.

The SBIZ file is a 2026-06 snapshot, so these features describe the current
state and must not be used to validate 2025 sales predictions.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

SNAPSHOT_DATE = "2026-06-30"

# Draft groups for the 9/29 taxonomy. Cafes (non-alcoholic drinks) belong to
# the cafe owner; bars are kept as their own group until the leisure boundary
# is agreed.
POINT_GROUPS = {
    "food_meal": {"major": {"음식"}, "exclude_middle": {"비알코올", "주점"}},
    "food_bar": {"major": {"음식"}, "middle": {"주점"}},
    "shopping_destination": {
        "middle": {
            "섬유·의복·신발 소매", "가전·통신 소매", "시계·귀금속 소매", "안경·정밀기기 소매", "가구 소매",
        },
        "minor": {
            "화장품 소매업", "운동용품 소매업", "장난감 소매업", "음반/비디오물 소매업", "자전거 소매업",
            "예술품 소매업", "기념품점", "주방/가정용품 소매업", "악기 소매업",
        },
    },
    "shopping_daily": {
        "middle": {"식료품 소매"},
        "minor": {"편의점", "슈퍼마켓", "약국"},
    },
}

# Official-area service codes used for sales productivity.
AREA_SALES_INDUSTRIES = {
    "food_meal": {
        "한식음식점", "중식음식점", "일식음식점", "양식음식점", "분식전문점", "치킨전문점", "패스트푸드점", "제과점",
    },
    "shopping_destination": {
        "일반의류", "화장품", "신발", "가방", "시계및귀금속", "안경", "가전제품", "가구", "운동/경기용품", "완구",
        "유아의류", "한복점", "악기", "예술품", "컴퓨터및주변장치판매", "핸드폰",
    },
}

# Industries where one official area can host a wholesale market. Fresh-food
# wholesale shows up in any area type; apparel wholesale only in market-type
# areas (e.g. Dongdaemun malls), because department stores and luxury streets
# also have very high per-store apparel sales but are genuine retail.
FOOD_WHOLESALE = {"청과상", "수산물판매", "육류판매", "미곡판매"}
APPAREL_WHOLESALE = {"일반의류", "섬유제품", "가방", "신발"}
WHOLESALE_PRONE = FOOD_WHOLESALE | APPAREL_WHOLESALE
MARKET_AREA_TYPE = "전통시장"
WHOLESALE_MIN_STORES = 20
WHOLESALE_PRODUCTIVITY_RATIO = 8.0

LQ_PRIOR_STORES = 30
# Smoothing added to polygon area so 0.002km2 market buildings do not explode.
DENSITY_SMOOTHING_KM2 = 0.05
SUPPLY_WEIGHTS = {"inside_density": 0.4, "walk_density": 0.3, "lq": 0.3}
MIN_SALES_COVERAGE = 0.5


def assign_point_group(major: str, middle: str, minor: str) -> str | None:
    """Return the draft group for one SBIZ store, or None when out of scope."""
    middle = str(middle).strip()
    for group, rule in POINT_GROUPS.items():
        if "major" in rule and major not in rule["major"]:
            continue
        if middle in rule.get("exclude_middle", set()):
            continue
        if "middle" in rule or "minor" in rule:
            if middle in rule.get("middle", set()) or minor in rule.get("minor", set()):
                return group
            continue
        return group
    return None


def shrunk_location_quotient(group_count: pd.Series, total_count: pd.Series, city_share: float, prior: float = LQ_PRIOR_STORES) -> pd.Series:
    """Specialisation vs. Seoul, pulled toward 1 when an area has few stores."""
    return ((group_count + prior * city_share) / (total_count + prior)) / city_share


def productivity_signal(sales: pd.Series, disclosed_stores: pd.Series, purpose_stores: pd.Series) -> pd.DataFrame:
    """Per-store sales from disclosed cells; unreliable coverage becomes NaN."""
    coverage = np.divide(disclosed_stores, purpose_stores, out=np.zeros(len(sales)), where=purpose_stores > 0)
    per_store = np.divide(sales, disclosed_stores, out=np.full(len(sales), np.nan), where=disclosed_stores > 0)
    per_store = pd.Series(per_store, index=sales.index)
    valid = per_store.notna()
    if valid.any():
        low, high = np.nanpercentile(per_store[valid], [1, 95])
        per_store = per_store.clip(low, high)
    per_store[coverage < MIN_SALES_COVERAGE] = np.nan
    return pd.DataFrame({"sales_coverage": coverage, "sales_per_store": per_store}, index=sales.index)


def flag_wholesale(area_rows: pd.DataFrame) -> pd.DataFrame:
    """Flag areas whose wholesale-prone industries sell far above the Seoul norm.

    `area_rows` needs area_code, area_type, industry, stores, sales for every
    Seoul area so that the per-store median is city-wide, not limited to the
    candidates.
    """
    rows = area_rows[area_rows.industry.isin(WHOLESALE_PRONE) & (area_rows.stores > 0) & area_rows.sales.notna()].copy()
    rows["per_store"] = rows.sales / rows.stores
    rows["ratio"] = rows.per_store / rows.groupby("industry").per_store.transform("median")
    eligible = rows.industry.isin(FOOD_WHOLESALE) | (rows.area_type == MARKET_AREA_TYPE)
    hits = rows[eligible & (rows.stores >= WHOLESALE_MIN_STORES) & (rows.ratio >= WHOLESALE_PRODUCTIVITY_RATIO)]
    reasons = hits.groupby("area_code").apply(
        lambda frame: "; ".join(f"{i} x{r:.0f}" for i, r in zip(frame.industry, frame.ratio)), include_groups=False
    )
    return pd.DataFrame({"wholesale_flag": True, "wholesale_reason": reasons})


def count_points(points: gpd.GeoDataFrame, areas: gpd.GeoDataFrame, buffer_m: float) -> pd.DataFrame:
    """Count grouped stores inside each polygon and inside polygon+buffer."""
    buffered = areas[["area_code", "geometry"]].copy()
    buffered["geometry"] = buffered.buffer(buffer_m)
    out = pd.DataFrame(index=pd.Index(areas.area_code, name="area_code"))
    out["polygon_km2"] = areas.area.values / 1e6
    out["footprint_km2"] = buffered.area.values / 1e6
    for label, polygons in [("inside", areas[["area_code", "geometry"]]), ("buffer400", buffered)]:
        joined = gpd.sjoin(points[["group", "geometry"]], polygons, predicate="within")
        counts = joined.groupby(["area_code", "group"]).size().unstack(fill_value=0)
        for group in counts.columns:
            out[f"{group}_{label}_count"] = counts[group]
        out[f"all_{label}_count"] = joined.groupby("area_code").size()
    return out.fillna(0)


def _percentile(values: pd.Series) -> pd.Series:
    return values.rank(pct=True) * 100


def score_purpose(features: pd.DataFrame, group: str, city_share: float) -> pd.DataFrame:
    count = features[f"{group}_buffer400_count"]
    out = pd.DataFrame(index=features.index)
    out[f"{group}_inside_density"] = features[f"{group}_inside_count"] / (features.polygon_km2 + DENSITY_SMOOTHING_KM2)
    out[f"{group}_walk_density"] = count / features.footprint_km2
    out[f"{group}_lq"] = shrunk_location_quotient(count, features.all_buffer400_count, city_share)
    supply = (
        SUPPLY_WEIGHTS["inside_density"] * _percentile(out[f"{group}_inside_density"])
        + SUPPLY_WEIGHTS["walk_density"] * _percentile(out[f"{group}_walk_density"])
        + SUPPLY_WEIGHTS["lq"] * _percentile(out[f"{group}_lq"])
    )
    demand = _percentile(np.log(features[f"{group}_sales_per_store"]))
    out[f"{group}_sales_signal_missing"] = demand.isna()
    out[f"{group}_supply_v1"] = supply
    out[f"{group}_score_v1"] = 0.7 * supply + 0.3 * demand.fillna(50.0)
    return out


def read_zip_csv(path: Path, encoding: str = "cp949") -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        with archive.open(members[0]) as source:
            return pd.read_csv(source, encoding=encoding, low_memory=False)


def read_sbiz_seoul(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename.encode("cp437").decode("cp949", errors="replace")
            if "서울" in name and name.endswith(".csv"):
                with archive.open(info) as source:
                    return pd.read_csv(source, low_memory=False)
    raise ValueError(f"No Seoul CSV in {path}")


def build(sbiz: pd.DataFrame, areas: gpd.GeoDataFrame, area_sales: pd.DataFrame, area_stores: pd.DataFrame, quarter: int, buffer_m: float) -> tuple[pd.DataFrame, dict]:
    sbiz = sbiz.copy()
    sbiz["group"] = [
        assign_point_group(a, b, c)
        for a, b, c in zip(sbiz["상권업종대분류명"], sbiz["상권업종중분류명"], sbiz["상권업종소분류명"])
    ]
    points = gpd.GeoDataFrame(
        sbiz[["group"]].fillna("other"), geometry=gpd.points_from_xy(sbiz["경도"], sbiz["위도"]), crs=4326
    ).to_crs(areas.crs)
    features = count_points(points, areas, buffer_m)

    stores = area_stores[area_stores.stdr_yyqu_cd == quarter].rename(
        columns={"trdar_cd": "area_code", "trdar_se_cd_nm": "area_type", "svc_induty_cd_nm": "industry", "stor_co": "stores"}
    )
    sales = area_sales[area_sales["기준_년분기_코드"] == quarter].rename(
        columns={"상권_코드": "area_code", "서비스_업종_코드_명": "industry", "당월_매출_금액": "sales"}
    )
    for frame in (stores, sales):
        frame["area_code"] = frame.area_code.astype(str).str.zfill(7)
    rows = stores[["area_code", "area_type", "industry", "stores"]].merge(
        sales[["area_code", "industry", "sales"]], on=["area_code", "industry"], how="left"
    )
    wholesale = flag_wholesale(rows)
    features = features.join(wholesale)
    features["wholesale_flag"] = features.wholesale_flag.fillna(False).astype(bool)

    for group, industries in AREA_SALES_INDUSTRIES.items():
        purpose = rows[rows.industry.isin(industries)]
        agg = purpose.groupby("area_code").agg(
            purpose_stores=("stores", "sum"),
            disclosed_stores=("stores", lambda s: s[purpose.loc[s.index, "sales"].notna()].sum()),
            sales=("sales", "sum"),
        ).reindex(features.index).fillna(0)
        signal = productivity_signal(agg.sales, agg.disclosed_stores, agg.purpose_stores)
        if group.startswith("shopping"):
            # Wholesale turnover is not a retail visit signal.
            signal.loc[features.wholesale_flag, "sales_per_store"] = np.nan
        features[f"{group}_sales_coverage"] = signal.sales_coverage
        features[f"{group}_sales_per_store"] = signal.sales_per_store

    city_counts = points.group.value_counts()
    for group in AREA_SALES_INDUSTRIES:
        features = features.join(score_purpose(features, group, city_counts.get(group, 0) / len(points)))

    features["feature_snapshot_date"] = SNAPSHOT_DATE
    features["historical_2025_use_allowed"] = False
    log_area = np.log(features.polygon_km2)
    summary = {
        "area_count": int(len(features)),
        "sales_quarter": quarter,
        "buffer_m": buffer_m,
        "wholesale_flag_count": int(features.wholesale_flag.sum()),
        **{
            f"{group}_score_v1_spearman_log_polygon_km2": round(float(features[f"{group}_score_v1"].corr(log_area, method="spearman")), 3)
            for group in AREA_SALES_INDUSTRIES
        },
        **{
            f"{group}_sales_signal_missing_count": int(features[f"{group}_sales_signal_missing"].sum())
            for group in AREA_SALES_INDUSTRIES
        },
    }
    return features.reset_index(), summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sbiz-zip", type=Path, required=True, help="소상공인시장진흥공단_상가(상권)정보 ZIP (2026-06-30)")
    parser.add_argument("--areas", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"))
    parser.add_argument("--area-sales", type=Path, default=Path("data/raw/commercial_area/commercial_sales_2025.zip"))
    parser.add_argument("--area-stores", type=Path, default=Path("data/raw/commercial_area/commercial_store_2025.zip"))
    parser.add_argument("--quarter", type=int, default=20254)
    parser.add_argument("--buffer-m", type=float, default=400)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/food_shopping_size_neutral"))
    args = parser.parse_args()

    areas = gpd.read_file(args.areas).to_crs(5181)
    areas["area_code"] = areas.area_code.astype(str).str.zfill(7)
    features, summary = build(
        read_sbiz_seoul(args.sbiz_zip), areas, read_zip_csv(args.area_sales), read_zip_csv(args.area_stores), args.quarter, args.buffer_m
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.output_dir / "official_area_food_shopping_size_neutral.csv", index=False, encoding="utf-8-sig")
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
