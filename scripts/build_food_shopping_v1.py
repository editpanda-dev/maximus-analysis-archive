"""Build the 786-area food and shopping scorecard v1 (Purpose Score v2 rules).

Score flow (team rule fixed on 2026-10-01, docs/feedback/2026-10-01_*):

    supply U  = 0.4 P(inside density) + 0.3 P(400m walk-area density) + 0.3 P(shrunk LQ)
    demand V  = P(log sales per store), only where disclosed sales cover >=30% of stores
    score     = 0.7 U + 0.3 V   (sales_status observed / estimated)
              = U               (sales_status missing; ranked separately, never filled with 50)

Every unit is scored the same way: six meal subtypes (M1-M6), five shopping
subtypes (SH1-SH5) and the two purposes (food = M1-M6, shopping = SH1-SH4).
Point counts come from the SBIZ store file (2026-06 snapshot, has coordinates);
store and sales totals come from the official 2025 Q4 area files.

The SBIZ snapshot describes the current state and must not be used to validate
2025 sales predictions.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from itertools import product
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

SNAPSHOT_DATE = "2026-06-30"
OUTPUT_PREFIX = "food_shopping_v1"

# Subtypes follow docs/food_shopping_taxonomy_draft.md. Each SBIZ minor code and
# each official industry belongs to at most one subtype. Bakery/dessert and
# cafes go to the cafe owner, bars to leisure, staff canteens are not public.
SUBTYPES = {
    "M1": {
        "label": "한식", "purpose": "food", "industries": {"한식음식점"},
        "sbiz": {f"I201{n:02d}" for n in range(1, 14)} | {"I20199"},
    },
    "M2": {"label": "중식", "purpose": "food", "industries": {"중식음식점"}, "sbiz": {"I20201", "I20202"}},
    "M3": {"label": "일식", "purpose": "food", "industries": {"일식음식점"}, "sbiz": {"I20301", "I20302", "I20303", "I20399"}},
    "M4": {
        "label": "양식·외국식", "purpose": "food", "industries": {"양식음식점"},
        "sbiz": {"I20401", "I20402", "I20403", "I20499", "I20501", "I20599", "I20601", "I20702"},
    },
    "M5": {
        "label": "간편식", "purpose": "food", "industries": {"분식전문점", "패스트푸드점"},
        "sbiz": {"I21003", "I21004", "I21005", "I21007", "I21099"},
    },
    "M6": {"label": "치킨", "purpose": "food", "industries": {"치킨전문점"}, "sbiz": {"I21006"}},
    "SH1": {
        "label": "패션·뷰티", "purpose": "shopping",
        "industries": {"일반의류", "신발", "가방", "화장품", "안경", "시계및귀금속", "한복점", "유아의류"},
        "sbiz": {"G20901", "G20902", "G20903", "G20904", "G20905", "G20907", "G20908", "G20910", "G20911", "G21701", "G21602", "G21503"},
    },
    "SH2": {
        "label": "디지털·가전", "purpose": "shopping", "industries": {"가전제품", "핸드폰", "컴퓨터및주변장치판매"},
        "sbiz": {"G20801", "G20802", "G20803", "G21603"},
    },
    "SH3": {
        "label": "홈·리빙", "purpose": "shopping", "industries": {"가구", "인테리어", "조명용품", "섬유제품"},
        "sbiz": {"G21101", "G21201", "G21202", "G20906", "G20909", "G21002"},
    },
    "SH4": {
        "label": "취미·문화", "purpose": "shopping", "industries": {"완구", "악기", "예술품", "화초", "운동/경기용품"},
        "sbiz": {"G21304", "G21305", "G21306", "G21203", "G21801", "G21802", "G21901", "G21303"},
    },
    # Grocery/daily needs: scored as a subtype only, kept out of the shopping purpose.
    "SH5": {
        "label": "장보기·생활", "purpose": None,
        "industries": {"슈퍼마켓", "편의점", "청과상", "수산물판매", "육류판매", "반찬가게", "미곡판매", "의약품"},
        "sbiz": {"G20404", "G20405", "G20501", "G20503", "G20504", "G20505", "G20506", "G20508", "G20509", "G21501"},
    },
}
PURPOSES = {
    "food": {"label": "식사", "subtypes": ["M1", "M2", "M3", "M4", "M5", "M6"]},
    "shopping": {"label": "쇼핑", "subtypes": ["SH1", "SH2", "SH3", "SH4"]},
}
# QA-only unit: food without delivery-heavy subtypes.
SENSITIVITY_UNITS = {"food_no_delivery": ["M1", "M2", "M3", "M4"]}
DELIVERY_PRONE = {"M5", "M6"}

# Codes that belong to another purpose's base score; they must never enter ours.
OTHER_PURPOSE_INDUSTRIES = {"제과점", "커피-음료", "호프-간이주점"}
OTHER_PURPOSE_SBIZ = {"I21001", "I21002", "I21008", "I21201", "I21101", "I21102", "I21103", "I21104", "I20701"}

SUPPLY_WEIGHTS = {"inside_density": 0.4, "walk_density": 0.3, "lq": 0.3}
SUPPLY_SHARE = 0.7
SALES_OBSERVED_MIN = 0.7
SALES_ESTIMATED_MIN = 0.3
LQ_PRIOR_STORES = 30
# Smoothing added to polygon area so 0.002km2 market buildings do not explode.
DENSITY_SMOOTHING_KM2 = 0.05
SMALL_AREA_STORES = 50
WIDE_AREA_M = 1000
OVERLAP_SHARE = 0.3
TOURISM_TYPE = "관광특구"
TOURISM_INNER_SHARE = 0.5
TOP_N = 10
# Reason sentences only name a supply strength at or above this percentile.
REASON_MIN_PERCENTILE = 70
# Combo Top lists: every purpose must be at least median, so one strong purpose
# cannot carry a weak one.
COMBO_MIN_PERCENTILE = 50
# Subtype Top lists only: a handful of stores in a tiny polygon is not a destination.
MIN_SUBTYPE_TOP_STORES = 5

# Automatic wholesale candidates: per-store sales >= 8x the Seoul median of the
# same industry with >= 20 stores. Fresh food counts in any area type, apparel
# only in market-type areas (department stores also sell a lot per store).
# Candidates are confirmed by the manual review file, not used directly.
FOOD_WHOLESALE = {"청과상", "수산물판매", "육류판매", "미곡판매"}
APPAREL_WHOLESALE = {"일반의류", "섬유제품", "가방", "신발"}
MARKET_AREA_TYPE = "전통시장"
WHOLESALE_MIN_STORES = 20
WHOLESALE_PRODUCTIVITY_RATIO = 8.0
# Final review decision -> units whose sales signal and Top-K eligibility are removed.
WHOLESALE_EFFECT = {"wholesale_apparel": ["shopping", "SH1"], "wholesale_food": ["SH5"], "retail": []}

SBIZ_TO_SUBTYPE = {code: subtype for subtype, rule in SUBTYPES.items() for code in rule["sbiz"]}
INDUSTRY_TO_SUBTYPE = {name: subtype for subtype, rule in SUBTYPES.items() for name in rule["industries"]}


def unit_subtypes(unit: str) -> list[str]:
    if unit in PURPOSES:
        return PURPOSES[unit]["subtypes"]
    if unit in SENSITIVITY_UNITS:
        return SENSITIVITY_UNITS[unit]
    return [unit]


def unit_label(unit: str) -> str:
    return PURPOSES[unit]["label"] if unit in PURPOSES else SUBTYPES[unit]["label"]


def spearman(a: pd.Series, b: pd.Series) -> float:
    """Spearman rho without scipy: Pearson on average ranks."""
    return a.rank().corr(b.rank())


def percentile(values: pd.Series) -> pd.Series:
    """Average-rank percentile x100 among non-missing values."""
    return values.rank(pct=True) * 100


def shrunk_location_quotient(group_count: pd.Series, total_count: pd.Series, city_share: float, prior: float = LQ_PRIOR_STORES) -> pd.Series:
    """Specialisation vs. Seoul, pulled toward 1 when an area has few stores."""
    return ((group_count + prior * city_share) / (total_count + prior)) / city_share


def sales_status(coverage: pd.Series) -> pd.Series:
    status = np.select(
        [coverage >= SALES_OBSERVED_MIN, coverage >= SALES_ESTIMATED_MIN], ["observed", "estimated"], default="missing"
    )
    return pd.Series(status, index=coverage.index)


def productivity_signal(
    sales: pd.Series, expected_sales: pd.Series, disclosed_stores: pd.Series, purpose_stores: pd.Series
) -> pd.DataFrame:
    """Mix-adjusted sales productivity plus the three-level sales status.

    `expected_sales` is, over the disclosed cells, stores x the Seoul median
    per-store sales of each industry. The index (actual / expected) therefore
    compares an area with what the same industry mix sells elsewhere, so a
    snack-bar-heavy area is not penalised for selling cheaper meals than a
    Korean-restaurant-heavy one. Undisclosed cells are missing, not zero; below
    30% coverage the index is dropped and the area is ranked on supply only.
    """
    coverage = pd.Series(
        np.divide(disclosed_stores, purpose_stores, out=np.zeros(len(sales)), where=purpose_stores > 0), index=sales.index
    )
    index = pd.Series(
        np.divide(sales, expected_sales, out=np.full(len(sales), np.nan), where=expected_sales > 0), index=sales.index
    )
    status = sales_status(coverage)
    index[status == "missing"] = np.nan
    return pd.DataFrame({"sales_coverage": coverage, "sales_index": index, "sales_status": status})


def flag_wholesale_candidates(area_rows: pd.DataFrame) -> pd.DataFrame:
    """Automatic wholesale candidates; `area_rows` must cover every Seoul area."""
    rows = area_rows[
        area_rows.industry.isin(FOOD_WHOLESALE | APPAREL_WHOLESALE) & (area_rows.stores > 0) & area_rows.sales.notna()
    ].copy()
    rows["per_store"] = rows.sales / rows.stores
    rows["ratio"] = rows.per_store / rows.groupby("industry").per_store.transform("median")
    eligible = rows.industry.isin(FOOD_WHOLESALE) | (rows.area_type == MARKET_AREA_TYPE)
    hits = rows[eligible & (rows.stores >= WHOLESALE_MIN_STORES) & (rows.ratio >= WHOLESALE_PRODUCTIVITY_RATIO)]
    reasons = hits.groupby("area_code").apply(
        lambda frame: "; ".join(f"{i} x{r:.0f}" for i, r in zip(frame.industry, frame.ratio)), include_groups=False
    )
    return pd.DataFrame({"wholesale_auto_candidate": True, "wholesale_auto_reason": reasons})


def apply_wholesale_review(candidates: pd.DataFrame, review: pd.DataFrame, strict: bool = True) -> pd.DataFrame:
    """Join manual review decisions; every automatic candidate must be reviewed.

    `strict=False` is only for other-quarter sensitivity runs, where new
    candidates fall back to retail.
    """
    review = review.set_index("area_code")
    unknown = sorted(set(candidates.index) - set(review.index))
    if unknown and strict:
        raise ValueError(f"Wholesale candidates without a review decision: {unknown}")
    bad = sorted(set(review.review_decision) - set(WHOLESALE_EFFECT))
    if bad:
        raise ValueError(f"Unknown wholesale review decisions: {bad}")
    out = candidates.join(review[["review_decision", "review_note"]], how="outer")
    out["wholesale_auto_candidate"] = out.wholesale_auto_candidate.fillna(False).astype(bool)
    return out.rename(columns={"review_decision": "wholesale_decision", "review_note": "wholesale_note"})


def count_points(points: gpd.GeoDataFrame, areas: gpd.GeoDataFrame, buffer_m: float) -> pd.DataFrame:
    """Count subtype stores inside each polygon (boundary included) and inside polygon+buffer."""
    buffered = areas[["area_code", "geometry"]].copy()
    buffered["geometry"] = buffered.buffer(buffer_m)
    out = pd.DataFrame(index=pd.Index(areas.area_code, name="area_code"))
    out["polygon_km2"] = areas.area.values / 1e6
    out["footprint_km2"] = buffered.area.values / 1e6
    for label, polygons in [("inside", areas[["area_code", "geometry"]]), ("walk", buffered)]:
        # `intersects` keeps stores on the boundary that `within` used to drop.
        joined = gpd.sjoin(points[["subtype", "geometry"]], polygons, predicate="intersects")
        counts = joined.groupby(["area_code", "subtype"]).size().unstack(fill_value=0)
        for subtype in counts.columns:
            out[f"{subtype}_{label}_count"] = counts[subtype]
        out[f"all_{label}_count"] = joined.groupby("area_code").size()
    return out.fillna(0)


def score_unit(features: pd.DataFrame, unit: str, city_share: float) -> pd.DataFrame:
    parts = unit_subtypes(unit)
    inside = sum(features[f"{s}_inside_count"] for s in parts)
    walk = sum(features[f"{s}_walk_count"] for s in parts)
    out = pd.DataFrame(index=features.index)
    if unit not in SUBTYPES:  # subtype counts already come from count_points
        out[f"{unit}_inside_count"] = inside
        out[f"{unit}_walk_count"] = walk
    out[f"{unit}_inside_density"] = inside / (features.polygon_km2 + DENSITY_SMOOTHING_KM2)
    out[f"{unit}_walk_density"] = walk / features.footprint_km2
    out[f"{unit}_lq"] = shrunk_location_quotient(walk, features.all_walk_count, city_share)
    for key in SUPPLY_WEIGHTS:
        out[f"{unit}_p_{key}"] = percentile(out[f"{unit}_{key}"])
    # No stores means no supply: tied zeros would otherwise share an average
    # rank of ~30 and a subtype an area does not have would still score.
    out.loc[inside == 0, f"{unit}_p_inside_density"] = 0.0
    out.loc[walk == 0, f"{unit}_p_walk_density"] = 0.0
    supply = sum(weight * out[f"{unit}_p_{key}"] for key, weight in SUPPLY_WEIGHTS.items())
    demand = percentile(features[f"{unit}_sales_index"])
    has_demand = demand.notna()
    out[f"{unit}_supply"] = supply
    out[f"{unit}_demand"] = demand
    out[f"{unit}_score"] = np.where(has_demand, SUPPLY_SHARE * supply + (1 - SUPPLY_SHARE) * demand, supply)
    out[f"{unit}_score_basis"] = np.where(has_demand, "full", "supply_only")
    return out


def josa(word: str, with_batchim: str, without: str) -> str:
    """Pick a Korean particle from the last Hangul syllable of a name."""
    stem = re.sub(r"\s*\([^)]*\)\s*$", "", str(word)).strip()
    hangul = [c for c in stem if "가" <= c <= "힣"]
    if not hangul:
        return f"{with_batchim}({without})"
    return with_batchim if (ord(hangul[-1]) - ord("가")) % 28 else without


def access_sentence(ratio: float) -> str:
    if ratio >= 0.9:
        return "아침·오후·저녁 모두 동대문구 대부분의 출발지에서 대중교통 30분 안에 도착할 수 있어요."
    if ratio >= 0.5:
        return "아침·오후·저녁 모두 동대문구 출발지의 절반 이상에서 대중교통 30분 안에 도착할 수 있어요."
    return f"아침·오후·저녁 모두 동대문구 출발지의 약 {ratio * 100:.0f}%에서 대중교통 30분 안에 도착할 수 있어요."


STATUS_SENTENCE = {
    "observed": "관련 업종의 매출과 점포 구성이 충분히 관측됐어요.",
    "estimated": "점포 구성과 일부 공개 매출을 함께 반영했어요.",
    "missing": "매출 공개가 부족해 점포 구성을 중심으로 평가했어요.",
}
SUPPLY_SENTENCE = {
    "food": {
        "inside_density": "음식점이 상권 안에 촘촘히 모여 있어요.",
        "walk_density": "상권 주변 400m 안에도 음식점이 많아 고를 곳이 많아요.",
        "lq": "서울 평균보다 음식점 비중이 높은 식사 특화 상권이에요.",
    },
    "shopping": {
        "inside_density": "소매 점포가 상권 안에 촘촘히 모여 있어요.",
        "walk_density": "상권 주변 400m 안에도 소매 점포가 많아 둘러볼 곳이 많아요.",
        "lq": "서울 평균보다 소매 점포 비중이 높은 쇼핑 특화 상권이에요.",
    },
}


def purpose_reason(row: pd.Series, purpose: str) -> str:
    name = row.area_name
    label = PURPOSES[purpose]["label"]
    strong = [SUBTYPES[s]["label"] for s in row[f"{purpose}_top_subtypes"].split("|") if s] if row[f"{purpose}_top_subtypes"] else []
    driver = max(SUPPLY_WEIGHTS, key=lambda key: row[f"{purpose}_p_{key}"])
    sentences = [f"{name}{josa(name, '은', '는')} {label} 점수 {row[f'{purpose}_score']:.0f}점이에요."]
    if strong:
        sentences.append(f"특히 {', '.join(strong)}{josa(strong[-1], '이', '가')} 강해요.")
    if row[f"{purpose}_p_{driver}"] >= REASON_MIN_PERCENTILE:  # only claim a strength the data shows
        sentences.append(SUPPLY_SENTENCE[purpose][driver])
    sentences.append(STATUS_SENTENCE[row[f"{purpose}_sales_status"]])
    sentences.append(access_sentence(row.minimum_period_ratio))
    if purpose == "shopping" and row.wholesale_decision == "wholesale_apparel":
        sentences.append("도매 거래 비중이 높아 일반 쇼핑 추천에서는 제외했어요.")
    return " ".join(sentences)


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


def area_flags(areas: gpd.GeoDataFrame, stores: pd.DataFrame) -> pd.DataFrame:
    """Tourism scenarios, wide/small area flags. Rows are never dropped."""
    flags = pd.DataFrame(index=pd.Index(areas.area_code, name="area_code"))
    geom = areas.set_index("area_code").geometry
    is_tourism = areas.set_index("area_code").area_type_name.eq(TOURISM_TYPE)
    tourism = geom[is_tourism]
    inner = pd.Series(False, index=geom.index)
    parent = pd.Series("", index=geom.index)
    for code, zone in tourism.items():
        share = geom.intersection(zone).area / geom.area
        hit = (share >= TOURISM_INNER_SHARE) & ~is_tourism
        inner |= hit
        parent[hit] = code
    flags["is_tourism_zone"] = is_tourism
    flags["inside_tourism_zone"] = inner
    flags["tourism_parent_code"] = parent
    # Scenario C (default): drop only the six tourism polygons, keep the areas inside.
    flags["eligible_scenario_a_all"] = True
    flags["eligible_scenario_b_drop_tourism_and_inner"] = ~(is_tourism | inner)
    flags["recommendation_eligible"] = ~is_tourism
    long_side = geom.apply(lambda g: max(_rect_sides(g.minimum_rotated_rectangle)))
    flags["long_side_m"] = long_side.round(0)
    flags["wide_area"] = (long_side > WIDE_AREA_M) & ~is_tourism
    total = stores.groupby("area_code").stores.sum().reindex(flags.index).fillna(0)
    flags["official_store_count_2025q4"] = total
    flags["small_area"] = total < SMALL_AREA_STORES
    return flags


def _rect_sides(rect) -> list[float]:
    xs, ys = rect.exterior.coords.xy
    return [float(np.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i])) for i in range(len(xs) - 1)] or [0.0]


def pick_top(frame: pd.DataFrame, score_col: str, geom: gpd.GeoSeries, n: int = TOP_N) -> pd.DataFrame:
    """Top-n by score, skipping areas that overlap >=30% with a higher-ranked pick."""
    chosen: list[str] = []
    skipped: dict[str, str] = {}
    for code in frame.sort_values([score_col, "area_code"], ascending=[False, True]).index:
        g = geom[code]
        clash = next(
            (c for c in chosen if g.intersection(geom[c]).area / min(g.area, geom[c].area) >= OVERLAP_SHARE), None
        )
        if clash:
            skipped[code] = clash
            continue
        chosen.append(code)
        if len(chosen) == n:
            break
    out = frame.loc[chosen].copy()
    out["rank"] = range(1, len(out) + 1)
    out.attrs["skipped_overlap"] = skipped
    return out


def build(
    sbiz: pd.DataFrame,
    areas: gpd.GeoDataFrame,
    area_sales: pd.DataFrame,
    area_stores: pd.DataFrame,
    wholesale_review: pd.DataFrame,
    quarter: int,
    buffer_m: float,
    strict_review: bool = True,
) -> tuple[pd.DataFrame, dict]:
    sbiz = sbiz.copy()
    sbiz["subtype"] = sbiz["상권업종소분류코드"].map(SBIZ_TO_SUBTYPE).fillna("other")
    points = gpd.GeoDataFrame(
        sbiz[["subtype"]], geometry=gpd.points_from_xy(sbiz["경도"], sbiz["위도"]), crs=4326
    ).to_crs(areas.crs)
    features = count_points(points, areas, buffer_m)
    for subtype in SUBTYPES:
        for label in ("inside", "walk"):
            if f"{subtype}_{label}_count" not in features:
                features[f"{subtype}_{label}_count"] = 0

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
    rows["subtype"] = rows.industry.map(INDUSTRY_TO_SUBTYPE)

    candidates = flag_wholesale_candidates(rows)
    wholesale = apply_wholesale_review(candidates[candidates.index.isin(features.index)], wholesale_review, strict_review)
    disclosed = rows.sales.notna() & (rows.stores > 0)
    median_per_store = (rows.sales / rows.stores)[disclosed].groupby(rows.industry[disclosed]).median()
    rows["expected_sales"] = np.where(disclosed, rows.stores * rows.industry.map(median_per_store), 0.0)
    features = features.join(wholesale.drop(columns=[c for c in ["area_name"] if c in wholesale]))
    features["wholesale_auto_candidate"] = features.wholesale_auto_candidate.fillna(False).astype(bool)
    features["wholesale_decision"] = features.wholesale_decision.fillna("retail")
    features = features.join(area_flags(areas, stores))
    meta = areas.set_index("area_code")[["area_name", "area_type_name", "minimum_period_ratio", "access_tier"]]
    features = meta.join(features)

    units = list(SUBTYPES) + list(PURPOSES) + list(SENSITIVITY_UNITS)
    city_share = points.subtype.value_counts() / len(points)
    for unit in units:
        parts = unit_subtypes(unit)
        purpose_rows = rows[rows.subtype.isin(parts)]
        agg = purpose_rows.groupby("area_code").agg(
            purpose_stores=("stores", "sum"),
            disclosed_stores=("stores", lambda s: s[purpose_rows.loc[s.index, "sales"].notna()].sum()),
            sales=("sales", "sum"),
            expected_sales=("expected_sales", "sum"),
        ).reindex(features.index).fillna(0)
        signal = productivity_signal(agg.sales, agg.expected_sales, agg.disclosed_stores, agg.purpose_stores)
        blocked = features.wholesale_decision.map(lambda d: unit in WHOLESALE_EFFECT[d])
        signal.loc[blocked, "sales_index"] = np.nan
        signal.loc[blocked, "sales_status"] = "missing"
        features[f"{unit}_official_store_count"] = agg.purpose_stores
        features[f"{unit}_sales_coverage"] = signal.sales_coverage
        features[f"{unit}_sales_index"] = signal.sales_index
        features[f"{unit}_sales_status"] = signal.sales_status
        features = features.join(score_unit(features, unit, float(sum(city_share.get(s, 0) for s in parts))))

    # Strongest subtypes are judged on supply, which every area has; mixing
    # full and supply-only scores would compare two different scales. Sparse
    # subtypes jump with one or two stores, so MIN_SUBTYPE_TOP_STORES applies.
    subtype_scores = pd.DataFrame(
        {s: features[f"{s}_supply"].where(features[f"{s}_inside_count"] >= MIN_SUBTYPE_TOP_STORES) for s in SUBTYPES}
    )
    ordered = subtype_scores.apply(lambda r: r.dropna().sort_values(ascending=False).index.tolist(), axis=1)
    features["best_subtype"] = ordered.str[0].fillna("")
    features["best_subtype_label"] = features.best_subtype.map(lambda s: SUBTYPES[s]["label"] if s else "")
    features["best_subtype_score"] = subtype_scores.max(axis=1)
    features["top3_subtypes"] = ordered.map(lambda o: "|".join(o[:3]))
    features["top3_subtype_labels"] = ordered.map(lambda o: "|".join(SUBTYPES[s]["label"] for s in o[:3]))
    for purpose, rule in PURPOSES.items():
        sub = subtype_scores[rule["subtypes"]]
        best = sub.apply(lambda r: [s for s in r.dropna().sort_values(ascending=False).index if r[s] >= 70][:2], axis=1)
        features[f"{purpose}_best_subtype"] = sub.apply(lambda r: r.idxmax() if r.notna().any() else "", axis=1)
        features[f"{purpose}_top_subtypes"] = best.map("|".join)

    features["access_percentile"] = percentile(features.minimum_period_ratio)
    # Small areas (<50 official stores) stay listable on purpose: a small but
    # dense alley is exactly what the size correction is meant to surface.
    features["shopping_eligible"] = features.recommendation_eligible & (features.wholesale_decision != "wholesale_apparel")
    features["food_eligible"] = features.recommendation_eligible
    for purpose in PURPOSES:
        features[f"{purpose}_reason"] = features.apply(purpose_reason, axis=1, purpose=purpose)

    features["feature_snapshot_date"] = SNAPSHOT_DATE
    features["sales_quarter"] = quarter
    features["walk_distance_basis"] = f"euclidean_{int(buffer_m)}m_buffer"
    features["historical_2025_use_allowed"] = False
    summary = {"area_count": int(len(features)), "sales_quarter": quarter, "buffer_m": buffer_m}
    return features.reset_index(), summary


# ---------------------------------------------------------------- rankings

COMBOS = {
    "food+shopping": ["food", "shopping"],
    "food+cafe": ["food", "cafe"],
    "shopping+cafe": ["shopping", "cafe"],
    "food+cafe+shopping": ["food", "cafe", "shopping"],
}
PURPOSE_LABELS = {"food": "식사", "shopping": "쇼핑", "cafe": "카페(임시)"}


def attach_cafe(scorecard: pd.DataFrame, cafe: pd.DataFrame) -> pd.DataFrame:
    """Provisional cafe signal: Hanbyeol's 2026-09-29 size-adjusted supply score."""
    cafe = cafe.set_index("area_code")
    out = scorecard.set_index("area_code")
    out["cafe_score_provisional"] = cafe.cafe_size_adjusted_supply_only_score.reindex(out.index)
    out["cafe_draft_status"] = cafe.score_status.reindex(out.index)
    out["cafe_eligible"] = cafe.recommendation_eligible.reindex(out.index).fillna(False).astype(bool)
    return out.reset_index()


def combo_frame(scorecard: pd.DataFrame, weights: tuple[float, float] = (SUPPLY_SHARE, 0.0)) -> pd.DataFrame:
    """Purpose percentiles and combo scores. weights = (supply share, access share)."""
    supply_share, access_share = weights
    frame = scorecard.set_index("area_code")
    pct = pd.DataFrame(index=frame.index)
    for purpose in PURPOSES:
        full = supply_share * frame[f"{purpose}_supply"] + (1 - supply_share) * frame[f"{purpose}_demand"]
        score = full.where(frame[f"{purpose}_score_basis"] == "full", frame[f"{purpose}_supply"])
        score = (1 - access_share) * score + access_share * frame.access_percentile
        pct[purpose] = percentile(score)
        pct[f"{purpose}_score"] = score
    pct["cafe"] = percentile(frame.cafe_score_provisional)
    for name, members in COMBOS.items():
        pct[name] = pct[members].mean(axis=1)
        pct[f"{name}_weakest"] = pct[members].min(axis=1)
    return pct


def ranking_tables(scorecard: pd.DataFrame, geom: gpd.GeoSeries) -> dict[str, pd.DataFrame]:
    frame = scorecard.set_index("area_code")
    pct = combo_frame(scorecard)
    keep = ["area_name", "area_type_name", "minimum_period_ratio"]
    tables = {}

    purpose_rows = []
    for purpose in PURPOSES:
        eligible = frame[frame[f"{purpose}_eligible"]]
        for basis, n in [("full", 20), ("supply_only", 10)]:
            pool = eligible[eligible[f"{purpose}_score_basis"] == basis]
            top = pick_top(pool, f"{purpose}_score", geom, n)
            cols = keep + [
                f"{purpose}_score", f"{purpose}_supply", f"{purpose}_demand", f"{purpose}_sales_status",
                f"{purpose}_sales_coverage", f"{purpose}_top_subtypes", "best_subtype_label", f"{purpose}_reason",
            ]
            t = top[["rank"] + cols].rename(columns=lambda c: c.replace(f"{purpose}_", ""))
            t.insert(0, "list", f"{purpose}_{basis}")
            t.insert(1, "purpose", PURPOSES[purpose]["label"])
            t["pool_size"] = len(pool)
            t["skipped_overlap"] = "; ".join(f"{k}->{v}" for k, v in top.attrs["skipped_overlap"].items())
            purpose_rows.append(t.reset_index())
    tables["purpose_top"] = pd.concat(purpose_rows, ignore_index=True)

    subtype_rows = []
    for subtype, rule in SUBTYPES.items():
        # A wholesale decision already blanks the blocked unit's sales, so the
        # full-basis pool below drops those areas; SH5 has no purpose of its own.
        allowed = frame[f"{rule['purpose']}_eligible"] if rule["purpose"] else frame.recommendation_eligible
        eligible = frame[allowed & (frame[f"{subtype}_inside_count"] >= MIN_SUBTYPE_TOP_STORES) & ~frame.small_area]
        pool = eligible[eligible[f"{subtype}_score_basis"] == "full"]
        top = pick_top(pool, f"{subtype}_score", geom)
        t = top[["rank"] + keep + [f"{subtype}_score", f"{subtype}_sales_status", f"{subtype}_inside_count"]]
        t = t.rename(columns=lambda c: c.replace(f"{subtype}_", ""))
        t.insert(0, "subtype", subtype)
        t.insert(1, "subtype_label", rule["label"])
        t["pool_size"] = len(pool)
        subtype_rows.append(t.reset_index())
    tables["subtype_top"] = pd.concat(subtype_rows, ignore_index=True)

    combo_rows = []
    for name, members in COMBOS.items():
        merged = frame.join(pct[[name, f"{name}_weakest"] + [m for m in members]].add_prefix("pct_"))
        ok = pd.Series(True, index=merged.index)
        for m in members:
            ok &= merged["cafe_eligible"] if m == "cafe" else merged[f"{m}_eligible"]
        floor = np.logical_and.reduce([merged[f"pct_{m}"] >= COMBO_MIN_PERCENTILE for m in members])
        merged = merged[ok & floor]
        sales_members = [m for m in members if m != "cafe"]
        all_full = np.logical_and.reduce([merged[f"{m}_score_basis"] == "full" for m in sales_members])
        for basis, pool in [("all_sales_observed", merged[all_full]), ("includes_supply_only", merged[~all_full])]:
            top = pick_top(pool, f"pct_{name}", geom)
            cols = keep + [f"pct_{name}", f"pct_{name}_weakest"] + [f"pct_{m}" for m in members]
            cols += [f"{m}_score" for m in sales_members] + [f"{m}_sales_status" for m in sales_members]
            cols += ["top3_subtype_labels"]
            t = top[["rank"] + cols].rename(columns={f"pct_{name}": "combo_score", f"pct_{name}_weakest": "weakest_purpose_pct"})
            t.insert(0, "combo", name)
            t.insert(1, "combo_label", "+".join(PURPOSE_LABELS[m] for m in members))
            t.insert(2, "basis", basis)
            t["cafe_source"] = "hanbyeol_draft_20260929_supply_only" if "cafe" in members else ""
            t["pool_size"] = len(pool)
            t["reason"] = [combo_reason(frame.loc[c], members, pct.loc[c]) for c in t.index]
            combo_rows.append(t.reset_index())
    tables["combo_top"] = pd.concat(combo_rows, ignore_index=True)
    return tables


def combo_reason(row: pd.Series, members: list[str], pct: pd.Series) -> str:
    name = row.area_name
    plain = {m: PURPOSE_LABELS[m].replace("(임시)", "") for m in members}
    parts = [f"{plain[m]} 상위 {max(1, int(np.ceil(100 - pct[m])))}%" for m in members]
    text = f"{name}{josa(name, '은', '는')} {', '.join(parts)}에 들어 한 번에 여러 목적을 해결하기 좋아요."
    weakest = min(members, key=lambda m: pct[m])
    if pct[weakest] < 60:
        text += f" 다만 {plain[weakest]}{josa(plain[weakest], '은', '는')} 상대적으로 약해요."
    if any(m != "cafe" and row[f"{m}_score_basis"] == "supply_only" for m in members):
        text += " 일부 목적은 매출 공개가 부족해 점포 구성을 중심으로 평가했어요."
    return f"{text} {access_sentence(row.minimum_period_ratio)}"


def breakdown_table(scorecard: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Contribution of each input to the purpose score for every area in a Top list."""
    frame = scorecard.set_index("area_code")
    codes = set(tables["purpose_top"].area_code) | set(tables["combo_top"].area_code)
    rows = []
    for code in sorted(codes):
        r = frame.loc[code]
        for purpose in PURPOSES:
            full = r[f"{purpose}_score_basis"] == "full"
            share = SUPPLY_SHARE if full else 1.0
            entry = {"area_code": code, "area_name": r.area_name, "purpose": PURPOSES[purpose]["label"],
                     "score": r[f"{purpose}_score"], "score_basis": r[f"{purpose}_score_basis"],
                     "sales_status": r[f"{purpose}_sales_status"], "sales_coverage": r[f"{purpose}_sales_coverage"]}
            for key, weight in SUPPLY_WEIGHTS.items():
                entry[f"p_{key}"] = r[f"{purpose}_p_{key}"]
                entry[f"contrib_{key}"] = share * weight * r[f"{purpose}_p_{key}"]
            entry["p_sales_index"] = r[f"{purpose}_demand"]
            entry["contrib_sales_index"] = (1 - SUPPLY_SHARE) * r[f"{purpose}_demand"] if full else 0.0
            entry["inside_count"] = r[f"{purpose}_inside_count"]
            entry["walk_count"] = r[f"{purpose}_walk_count"]
            for s in PURPOSES[purpose]["subtypes"]:
                entry[f"{s}_{SUBTYPES[s]['label']}"] = r[f"{s}_score"]
            rows.append(entry)
    out = pd.DataFrame(rows)
    contrib = [c for c in out if c.startswith("contrib_")]
    out["contrib_check"] = out[contrib].sum(axis=1) - out.score
    return out


def tourism_scenarios(scorecard: pd.DataFrame, geom: gpd.GeoSeries) -> pd.DataFrame:
    frame = scorecard.set_index("area_code")
    pct = combo_frame(scorecard)
    frame["combo_food_shopping"] = pct["food+shopping"]
    scenarios = {
        "A_include_all": frame.eligible_scenario_a_all,
        "B_drop_tourism_and_inner": frame.eligible_scenario_b_drop_tourism_and_inner,
        "C_drop_tourism_polygon_only": frame.recommendation_eligible,
    }
    rows = []
    for target, col, extra in [
        ("food", "food_score", frame.food_score_basis == "full"),
        ("shopping", "shopping_score", (frame.shopping_score_basis == "full") & (frame.wholesale_decision != "wholesale_apparel")),
        ("food+shopping", "combo_food_shopping", (frame.food_score_basis == "full") & (frame.shopping_score_basis == "full") & (frame.wholesale_decision != "wholesale_apparel")),
    ]:
        tops = {k: pick_top(frame[mask & extra], col, geom) for k, mask in scenarios.items()}
        base = tops["C_drop_tourism_polygon_only"]
        for k, top in tops.items():
            common = set(top.index) & set(base.index)
            ranks = pd.concat([top["rank"], base["rank"]], axis=1, keys=["s", "b"]).dropna()
            rows.append({
                "target": target, "scenario": k, "top10": " | ".join(top.area_name),
                "kept_vs_C": len(common),
                "entered_vs_C": " | ".join(top.loc[sorted(set(top.index) - common)].area_name),
                "left_vs_C": " | ".join(base.loc[sorted(set(base.index) - common)].area_name),
                "rank_spearman_common_vs_C": round(float(spearman(ranks.s, ranks.b)), 3) if len(ranks) > 2 else np.nan,
                "tourism_in_top10": int(frame.loc[top.index].is_tourism_zone.sum()),
                "overlap_skipped": len(top.attrs["skipped_overlap"]),
            })
    return pd.DataFrame(rows)


def quarter_sensitivity(base: pd.DataFrame, others: dict[int, pd.DataFrame], geom: gpd.GeoSeries) -> pd.DataFrame:
    """Re-score with another 2025 quarter's stores and sales; compare Top 10 and ranks."""
    def tops(card: pd.DataFrame) -> dict[str, pd.DataFrame]:
        frame = card.set_index("area_code")
        return {p: pick_top(frame[frame[f"{p}_eligible"] & (frame[f"{p}_score_basis"] == "full")], f"{p}_score", geom) for p in PURPOSES}

    base_tops = tops(base)
    base_frame = base.set_index("area_code")
    rows = []
    for quarter, card in others.items():
        frame = card.set_index("area_code")
        for p, top in tops(card).items():
            common = frame.index[(frame[f"{p}_score_basis"] == "full") & (base_frame[f"{p}_score_basis"] == "full")]
            rows.append({
                "target": p, "quarter": quarter,
                "top10_kept_vs_base": len(set(top.index) & set(base_tops[p].index)),
                "spearman_vs_base_full_both": round(float(spearman(frame.loc[common, f"{p}_score"], base_frame.loc[common, f"{p}_score"])), 3),
                "full_basis_areas": int((frame[f"{p}_score_basis"] == "full").sum()),
                "top10": " | ".join(top.area_name),
            })
    return pd.DataFrame(rows)


SENSITIVITY_GRID = list(product([0.5, 0.7, 0.8], [0.0, 0.1, 0.2]))


def weight_sensitivity(scorecard: pd.DataFrame, geom: gpd.GeoSeries) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = scorecard.set_index("area_code")
    base_pct = combo_frame(scorecard)
    targets = {
        "food": (frame.food_eligible & (frame.food_score_basis == "full"), "food_score"),
        "shopping": (frame.shopping_eligible & (frame.shopping_score_basis == "full"), "shopping_score"),
        "food+shopping": (frame.food_eligible & frame.shopping_eligible & (frame.food_score_basis == "full") & (frame.shopping_score_basis == "full"), "food+shopping"),
    }
    base_tops = {t: pick_top(base_pct.loc[mask[mask].index], col, geom) for t, (mask, col) in targets.items()}
    rows, hits = [], {t: pd.Series(0, index=base_pct.index) for t in targets}
    for supply_share, access_share in SENSITIVITY_GRID:
        pct = combo_frame(scorecard, (supply_share, access_share))
        for t, (mask, col) in targets.items():
            pool = pct.loc[mask[mask].index]
            top = pick_top(pool, col, geom)
            hits[t][top.index] += 1
            rows.append({
                "target": t, "supply_share": supply_share, "demand_share": round(1 - supply_share, 2),
                "access_share": access_share,
                "top10_kept_vs_base": len(set(top.index) & set(base_tops[t].index)),
                "spearman_vs_base": round(float(spearman(pool[col], base_pct.loc[pool.index, col])), 3),
            })
    stability = []
    for t, top in base_tops.items():
        for code in top.index:
            n = int(hits[t][code])
            stability.append({"target": t, "area_code": code, "area_name": frame.loc[code].area_name,
                              "base_rank": int(top.loc[code, "rank"]), "top10_in_configs": n,
                              "configs": len(SENSITIVITY_GRID), "stability": "안정" if n >= 7 else "탐색"})
    return pd.DataFrame(rows), pd.DataFrame(stability)


# ---------------------------------------------------------------- QA

def qa_report(scorecard: pd.DataFrame, tables: dict[str, pd.DataFrame], sensitivity: pd.DataFrame, geom: gpd.GeoSeries) -> dict:
    frame = scorecard.set_index("area_code")
    units = list(SUBTYPES) + list(PURPOSES)
    score_cols = [f"{u}_score" for u in units]
    sbiz_codes = [c for rule in SUBTYPES.values() for c in rule["sbiz"]]
    industries = [c for rule in SUBTYPES.values() for c in rule["industries"]]
    log_area = np.log(frame.polygon_km2)
    full_food = frame.food_score_basis == "full"
    nd = frame.loc[full_food]
    top20 = lambda col, idx: set(frame.loc[idx].sort_values(col, ascending=False).head(20).index)  # noqa: E731
    pair_overlaps = 0
    for _, group in tables["purpose_top"].groupby("list"):
        codes = group.area_code.tolist()
        for i, a in enumerate(codes):
            for b in codes[i + 1:]:
                if geom[a].intersection(geom[b]).area / min(geom[a].area, geom[b].area) >= OVERLAP_SHARE:
                    pair_overlaps += 1
    checks = {
        "row_count": int(len(frame)),
        "row_count_is_786": len(frame) == 786,
        "area_code_unique": bool(frame.index.is_unique),
        "area_code_is_7_digit_string": bool(frame.index.str.fullmatch(r"\d{7}").all()),
        "score_missing": {c: int(frame[c].isna().sum()) for c in score_cols},
        "score_min": round(float(frame[score_cols].min().min()), 3),
        "score_max": round(float(frame[score_cols].max().max()), 3),
        "score_within_0_100": bool(((frame[score_cols] >= 0) & (frame[score_cols] <= 100)).all().all()),
        "supply_weights_sum": sum(SUPPLY_WEIGHTS.values()),
        "score_weights_sum": SUPPLY_SHARE + (1 - SUPPLY_SHARE),
        "sales_status_missing_label": int(sum(frame[f"{u}_sales_status"].isna().sum() for u in units)),
        "sales_status_counts": {u: frame[f"{u}_sales_status"].value_counts().to_dict() for u in units},
        "score_basis_counts": {u: frame[f"{u}_score_basis"].value_counts().to_dict() for u in units},
        "full_score_has_no_neutral_fill": bool(
            all((frame.loc[frame[f"{u}_score_basis"] == "supply_only", f"{u}_score"] == frame.loc[frame[f"{u}_score_basis"] == "supply_only", f"{u}_supply"]).all() for u in units)
        ),
        "sbiz_code_assigned_twice": len(sbiz_codes) - len(set(sbiz_codes)),
        "industry_assigned_twice": len(industries) - len(set(industries)),
        "other_purpose_codes_in_food_shopping": sorted((set(industries) & OTHER_PURPOSE_INDUSTRIES) | (set(sbiz_codes) & OTHER_PURPOSE_SBIZ)),
        "flags": {
            "is_tourism_zone": int(frame.is_tourism_zone.sum()),
            "inside_tourism_zone": int(frame.inside_tourism_zone.sum()),
            "wholesale_auto_candidate": int(frame.wholesale_auto_candidate.sum()),
            "wholesale_decision": frame.wholesale_decision.value_counts().to_dict(),
            "wide_area": int(frame.wide_area.sum()),
            "small_area": int(frame.small_area.sum()),
        },
        "spearman_score_vs_log_area": {p: round(float(spearman(frame[f"{p}_score"], log_area)), 3) for p in PURPOSES},
        "spearman_score_vs_official_store_count": {
            p: round(float(spearman(frame[f"{p}_score"], frame.official_store_count_2025q4)), 3) for p in PURPOSES
        },
        "delivery_sensitivity_food": {
            "spearman_full_basis": round(float(spearman(nd.food_score, nd.food_no_delivery_score)), 3),
            "top20_kept": len(top20("food_score", nd.index) & top20("food_no_delivery_score", nd.index)),
        },
        "top_list_overlap_pairs": pair_overlaps,
        "top_list_small_areas_info": int(frame.loc[pd.concat([tables["purpose_top"].area_code, tables["combo_top"].area_code])].small_area.sum()),
        "combo_rows_below_floor": int(
            (tables["combo_top"][[c for c in tables["combo_top"] if c.startswith("pct_")]] < COMBO_MIN_PERCENTILE).any(axis=1).sum()
        ),
        "zero_store_units_with_inside_percentile": int(
            sum(((frame[f"{u}_inside_count"] == 0) & (frame[f"{u}_p_inside_density"] > 0)).sum() for u in units)
        ),
        "top_list_tourism_polygons": int(frame.loc[tables["purpose_top"].area_code].is_tourism_zone.sum()),
        "top_list_apparel_wholesale_in_shopping": int(
            frame.loc[tables["purpose_top"].query("purpose == '쇼핑'").area_code].wholesale_decision.eq("wholesale_apparel").sum()
        ),
        "weight_sensitivity_min_top10_kept": sensitivity.groupby("target").top10_kept_vs_base.min().to_dict(),
    }
    checks["passed"] = bool(
        checks["row_count_is_786"] and checks["area_code_unique"] and checks["score_within_0_100"]
        and not any(checks["score_missing"].values()) and checks["sales_status_missing_label"] == 0
        and checks["sbiz_code_assigned_twice"] == 0 and checks["industry_assigned_twice"] == 0
        and not checks["other_purpose_codes_in_food_shopping"] and checks["top_list_overlap_pairs"] == 0
        and checks["top_list_tourism_polygons"] == 0 and checks["top_list_apparel_wholesale_in_shopping"] == 0
        and checks["full_score_has_no_neutral_fill"]
        and checks["combo_rows_below_floor"] == 0 and checks["zero_store_units_with_inside_percentile"] == 0
    )
    return checks


# ---------------------------------------------------------------- maps

MAP_LISTS = [
    ("food_full", "식사 Top 20", "purpose_top", "list == 'food_full'", "#c2410c"),
    ("shopping_full", "쇼핑 Top 20", "purpose_top", "list == 'shopping_full'", "#1d4ed8"),
    ("food+shopping", "식사+쇼핑 Top 10", "combo_top", "combo == 'food+shopping' and basis == 'all_sales_observed'", "#7c3aed"),
    ("food+cafe+shopping", "식사+카페+쇼핑 Top 10 (카페 임시)", "combo_top", "combo == 'food+cafe+shopping' and basis == 'all_sales_observed'", "#047857"),
]


CENTRAL_ANCHOR = "3120009"  # 종로3가역
CENTRAL_HALF_M = 3500


def write_maps(areas: gpd.GeoDataFrame, tables: dict[str, pd.DataFrame], out_dir: Path) -> None:
    import folium
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = ["AppleGothic", "NanumGothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    out_dir.mkdir(parents=True, exist_ok=True)
    wgs = areas.assign(geometry=areas.simplify(3)).to_crs(4326)  # 3m tolerance keeps the HTML small
    fmap = folium.Map(location=[37.565, 127.0], zoom_start=11, tiles="cartodbpositron")
    folium.GeoJson(wgs[["area_name", "geometry"]], name="후보 상권 786개",
                   style_function=lambda _: {"color": "#9ca3af", "weight": 0.5, "fillOpacity": 0.05},
                   tooltip=folium.GeoJsonTooltip(["area_name"], labels=False)).add_to(fmap)
    figs = {name: plt.subplots(2, 2, figsize=(14, 13)) for name in ("seoul", "central")}
    center = areas.set_index("area_code").geometry.loc[CENTRAL_ANCHOR].centroid
    for i, (key, title, table, query, color) in enumerate(MAP_LISTS):
        top = tables[table].query(query)[["area_code", "rank"]]
        layer = wgs.merge(top, on="area_code")
        group = folium.FeatureGroup(name=title, show=key == "food+shopping")
        folium.GeoJson(layer[["area_name", "rank", "geometry"]],
                       style_function=lambda _, c=color: {"color": c, "weight": 2, "fillColor": c, "fillOpacity": 0.45},
                       tooltip=folium.GeoJsonTooltip(["rank", "area_name"], aliases=["순위", "상권"])).add_to(group)
        for _, r in layer.iterrows():
            p = r.geometry.representative_point()
            folium.Marker([p.y, p.x], icon=folium.DivIcon(html=f'<div style="font:600 11px sans-serif;color:{color}">{r["rank"]}</div>')).add_to(group)
        group.add_to(fmap)
        layer_m = areas.merge(top, on="area_code")
        for name, (fig, axes) in figs.items():
            ax = axes.flat[i]
            areas.plot(ax=ax, color="#e5e7eb", edgecolor="#d1d5db", linewidth=0.2)
            layer_m.plot(ax=ax, color=color, edgecolor=color, linewidth=1.2, alpha=0.8)
            for _, r in layer_m.iterrows():
                p = r.geometry.representative_point()
                ax.annotate(f"{r['rank']}", (p.x, p.y), fontsize=8, color="#111827", ha="center", va="center",
                            bbox={"boxstyle": "circle,pad=0.15", "fc": "white", "ec": color, "lw": 0.8})
            if name == "central":
                ax.set_xlim(center.x - CENTRAL_HALF_M, center.x + CENTRAL_HALF_M)
                ax.set_ylim(center.y - CENTRAL_HALF_M * 0.8, center.y + CENTRAL_HALF_M * 0.8)
            ax.set_title(title, fontsize=13)
            ax.set_axis_off()
    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.save(out_dir / f"{OUTPUT_PREFIX}_top_map.html")
    for name, (fig, _) in figs.items():
        scope = "서울 전체" if name == "seoul" else "도심(종로·중구) 확대"
        fig.suptitle(f"식사·쇼핑 v1 상위 상권 · {scope} (2025년 4분기, 관광특구 폴리곤 제외, 겹침 30% 제거)", fontsize=14)
        fig.tight_layout()
        fig.savefig(out_dir / f"{OUTPUT_PREFIX}_top_map_{name}.png", dpi=160)
        plt.close(fig)


# ---------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sbiz-zip", type=Path, required=True, help="소상공인시장진흥공단_상가(상권)정보 ZIP (2026-06-30)")
    parser.add_argument("--areas", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"))
    parser.add_argument("--area-sales", type=Path, default=Path("data/raw/commercial_area/commercial_sales_2025.zip"))
    parser.add_argument("--area-stores", type=Path, default=Path("data/raw/commercial_area/commercial_store_2025.zip"))
    parser.add_argument("--wholesale-review", type=Path, default=Path("data/reference/food_shopping/food_shopping_wholesale_review_2025q4.csv"))
    parser.add_argument("--cafe-scores", type=Path, default=Path("data/reference/food_shopping/cafe_size_adjusted_score_draft_20260929.csv"))
    parser.add_argument("--quarter", type=int, default=20254)
    parser.add_argument("--buffer-m", type=float, default=400)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/food_shopping_v1"))
    args = parser.parse_args()

    areas = gpd.read_file(args.areas).to_crs(5181)
    areas["area_code"] = areas.area_code.astype(str).str.zfill(7)
    review = pd.read_csv(args.wholesale_review, dtype={"area_code": str})
    sbiz, sales, stores = read_sbiz_seoul(args.sbiz_zip), read_zip_csv(args.area_sales), read_zip_csv(args.area_stores)
    scorecard, summary = build(sbiz, areas, sales, stores, review, args.quarter, args.buffer_m)
    scorecard = attach_cafe(scorecard, pd.read_csv(args.cafe_scores, dtype={"area_code": str}))
    other_quarters = sorted(set(sales["기준_년분기_코드"]) - {args.quarter})
    others = {q: build(sbiz, areas, sales, stores, review, q, args.buffer_m, strict_review=False)[0] for q in other_quarters}
    geom = areas.set_index("area_code").geometry
    tables = ranking_tables(scorecard, geom)
    tables["score_breakdown_top"] = breakdown_table(scorecard, tables)
    tables["tourism_scenarios"] = tourism_scenarios(scorecard, geom)
    tables["weight_sensitivity"], tables["top10_stability"] = weight_sensitivity(scorecard, geom)
    tables["quarter_sensitivity"] = quarter_sensitivity(scorecard, others, geom)
    qa = qa_report(scorecard, tables, tables["weight_sensitivity"], geom)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    scorecard.drop(columns=[c for c in scorecard if c.startswith("food_no_delivery_")]).to_csv(
        out / f"official_area_{OUTPUT_PREFIX}_786.csv", index=False, encoding="utf-8-sig"
    )
    for name, table in tables.items():
        table.to_csv(out / f"{OUTPUT_PREFIX}_{name}.csv", index=False, encoding="utf-8-sig")
    (out / f"{OUTPUT_PREFIX}_qa.json").write_text(json.dumps({**summary, **qa}, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    write_maps(areas, tables, out / "maps")
    print(json.dumps({k: qa[k] for k in ["passed", "row_count", "score_min", "score_max", "flags", "spearman_score_vs_log_area"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
