#!/usr/bin/env python3
"""의외성(세렌디피티) 재순위화 SERP-v0.

관성 기준선(거리순·인기순·과거 유입순)과 같은 후보군(동대문구 출발 30분 접근
25% 이상 공식 상권 786곳) 위에서 다시 순위를 매긴다.

- 관련성 R: 상권 구조·이동 저항 변수로 예측한 목적별 매력도(목적 매출 Ridge 회귀의
  교차적합 예측값 백분위)와 접근성 백분위의 가중합. 공부는 매출 원천이 없어
  PATH-v0 공급 점수로 대체한다.
- 의외성 U: (1) 관측 유입이 구조로 기대되는 유입보다 낮은 정도(잔차),
  (2) 도시 전체 비인기(직전 분기 총매출 백분위의 역, Kotkov novelty),
  (3) 관성 Top-K와의 범주(업종 구성·상권 유형) 거리, (4) 관성 Top-K와의 공간 거리.
  (2)는 자체 검토에서 추가했다. 생활이동 유입이 행정동 단위 배분값이라 점포가 많은 유명 상권
  (이태원·동대문패션타운 관광특구)이 잔차만으로는 '덜 알려짐'으로 잘못 잡혔기 때문이다.
- 점수 S = R × U. R 하한 미만은 제외한다. 마지막으로 MMR로 다양성 재정렬한다.

복잡 모형은 쓰지 않는다(교수님 2026-09-09 피드백). 회귀는 numpy 닫힌 해 Ridge다.
저장소 안 공개 가공 데이터만 읽고 API를 부르지 않는다.

데이터 한계: 저장소 안 생활이동 유입은 **모든 출발지 합계(목적지 집계)**다.
동대문구발 OD가 없으므로 `nonroutine 유입 × 동대문구 출발지 30분 도달 비율`을
'동대문구발 유입 프록시'로 쓴다. B078 OD가 들어오면 이 열만 교체한다.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

PURPOSES = ["식사", "카페", "쇼핑", "여가문화", "공부"]
AREA_TYPES = ["골목상권", "발달상권", "전통시장", "관광특구"]
BASELINES = ["distance", "popularity", "past_inflow"]


@dataclass
class Config:
    top_k: int = 10                 # 관성 Top-K, 추천 Top-K
    r_floor: float = 0.6            # 목적 안 R 백분위 하한
    w_resid: float = 0.3            # U 가중치: 저유입 잔차
    w_novelty: float = 0.2          # U 가중치: 도시 전체 비인기(Kotkov novelty)
    w_cat: float = 0.25             # U 가중치: 범주 거리
    w_spatial: float = 0.25         # U 가중치: 공간 거리
    w_access: float = 0.2           # R 안 접근성 가중치(Huff 저항항)
    mmr_lambda: float = 0.7         # MMR 관련성-다양성 균형
    spatial_scale_km: float = 1.5   # 공간 유사도 감쇠 거리
    ridge_alpha: float = 1.0
    n_folds: int = 5
    weights_note: str = field(default="사전 지정값, 학습값 아님")


# ---------------------------------------------------------------------------
# 기본 연산
# ---------------------------------------------------------------------------

def pct_rank(s: pd.Series) -> pd.Series:
    """0~1 백분위(동점 평균). 상수열이면 0.5."""
    if s.nunique(dropna=True) <= 1:
        return pd.Series(0.5, index=s.index)
    return (s.rank(method="average") - 1) / (s.notna().sum() - 1)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def ridge_oof(X: np.ndarray, y: np.ndarray, folds: np.ndarray, alpha: float) -> np.ndarray:
    """표준화 + 닫힌 해 Ridge의 교차적합(out-of-fold) 예측."""
    pred = np.zeros_like(y, dtype=float)
    for f in np.unique(folds):
        tr, te = folds != f, folds == f
        mu, sd = X[tr].mean(0), X[tr].std(0)
        sd[sd == 0] = 1.0
        Xtr = np.c_[np.ones(tr.sum()), (X[tr] - mu) / sd]
        Xte = np.c_[np.ones(te.sum()), (X[te] - mu) / sd]
        pen = alpha * np.eye(Xtr.shape[1])
        pen[0, 0] = 0.0
        beta = np.linalg.solve(Xtr.T @ Xtr + pen, Xtr.T @ y[tr])
        pred[te] = Xte @ beta
    return pred


def area_folds(codes: pd.Series, n_folds: int) -> np.ndarray:
    return (pd.to_numeric(codes, errors="coerce").fillna(0).astype(np.int64) % n_folds).to_numpy()


def combine_scores(r: pd.Series, u: pd.Series, r_floor: float) -> pd.Series:
    """S = R × U. R < 하한이면 NaN(추천 제외)."""
    s = r * u
    return s.where(r >= r_floor)


def gini(values) -> float:
    x = np.sort(np.asarray(values, dtype=float))
    if x.size == 0 or x.sum() == 0:
        return 0.0
    n = x.size
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def overlap_at_k(a, b, k: int) -> float:
    """|A∩B| / k. A, B는 순서 있는 area_code 목록."""
    return len(set(list(a)[:k]) & set(list(b)[:k])) / float(k)


# ---------------------------------------------------------------------------
# 입력 구성
# ---------------------------------------------------------------------------

def polygon_centroid(coords) -> tuple[float, float]:
    ring = np.asarray(coords[0], dtype=float)
    x, y = ring[:, 0], ring[:, 1]
    cross = x[:-1] * y[1:] - x[1:] * y[:-1]
    a = cross.sum() / 2
    if abs(a) < 1e-15:
        return float(y.mean()), float(x.mean())
    cx = ((x[:-1] + x[1:]) * cross).sum() / (6 * a)
    cy = ((y[:-1] + y[1:]) * cross).sum() / (6 * a)
    return float(cy), float(cx)


def load_centroids(path: Path) -> pd.DataFrame:
    g = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for f in g["features"]:
        geom = f["geometry"]
        if geom["type"] == "Polygon":
            lat, lon = polygon_centroid(geom["coordinates"])
        else:  # MultiPolygon: 가장 큰 외곽 링
            polys = sorted(geom["coordinates"], key=lambda p: len(p[0]), reverse=True)
            lat, lon = polygon_centroid(polys[0])
        rows.append({"area_code": str(f["properties"]["area_code"]), "lat": lat, "lon": lon})
    return pd.DataFrame(rows)


def load_inputs(root: Path, quarter: int, use_movement: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(area_frame, purpose_frame)을 as-of 분기 기준으로 만든다.

    use_movement=True: 관측 유입 = 2026-08 생활이동 nonroutine 유입 × 접근률(동대문구발 프록시).
    use_movement=False(백테스트): 관측 유입 대신 as-of 분기 상권 총매출을 쓴다(미래 유입 누수 방지).
    """
    p = root / "data/processed"
    qf = pd.read_csv(p / "commercial_area_purpose_features/official_area_purpose_quarter_features.csv",
                     dtype={"area_code": str})
    gap = pd.read_csv(p / "commercial_area_sales_gap/official_area_sales_structure_gap_quarter.csv",
                      dtype={"area_code": str})
    cand = pd.read_csv(p / "commercial_area_accessibility/commercial_area_candidates_25pct.csv",
                       dtype={"area_code": str})
    cent = load_centroids(p / "commercial_area_accessibility/commercial_area_candidates_25pct.geojson")

    cur = qf[qf["quarter"] == quarter]
    if cur.empty:
        raise ValueError(f"quarter {quarter} not in purpose features")
    prev_q = sorted(q for q in qf["quarter"].unique() if q < quarter)
    prev = qf[qf["quarter"] == prev_q[-1]] if prev_q else None
    lag_q = prev_q[-1] if prev_q else quarter
    lag_sales = gap[gap["quarter"] == lag_q][["area_code", "sales_amount"]].rename(
        columns={"sales_amount": "lagged_total_sales"})

    share = cur.pivot(index="area_code", columns="purpose", values="purpose_store_share").add_prefix("share_")
    g = gap[gap["quarter"] == quarter][["area_code", "area_m2", "store_count", "industry_entropy", "sales_amount"]]
    area = (cand[["area_code", "area_name", "area_type_name", "primary_district_name", "mean_period_ratio",
                  "minimum_period_ratio"]]
            .merge(cent, on="area_code", how="left")
            .merge(g, on="area_code", how="left")
            .merge(share.reset_index(), on="area_code", how="left")
            .merge(lag_sales, on="area_code", how="left"))
    dd = area[area["primary_district_name"] == "동대문구"]
    ref_lat, ref_lon = dd["lat"].mean(), dd["lon"].mean()
    area["dist_km"] = haversine_km(ref_lat, ref_lon, area["lat"], area["lon"])
    area["log_store_total"] = np.log1p(area["store_count"].fillna(0))
    area["log_area_m2"] = np.log(area["area_m2"].clip(lower=1))
    area["industry_entropy"] = area["industry_entropy"].fillna(area["industry_entropy"].median())

    if use_movement:
        mv = pd.read_csv(p / "week2_integration/official_area_week2_integration.csv", dtype={"area_code": str})
        mv["inflow_nonroutine"] = mv[["movement_inflow_other", "movement_inflow_shopping",
                                      "movement_inflow_tourism", "movement_inflow_hospital"]].sum(axis=1)
        area = area.merge(mv[["area_code", "inflow_nonroutine", "movement_inflow_total"]], on="area_code", how="left")
        area["observed_inflow"] = area["inflow_nonroutine"] * area["mean_period_ratio"]
        area["observed_source"] = "생활이동 2026-08 nonroutine×접근률(동대문구발 프록시)"
    else:
        area["observed_inflow"] = area["sales_amount"].fillna(0)
        area["observed_source"] = f"{quarter} 상권 총매출(백테스트 대체)"
    area["log_observed"] = np.log1p(area["observed_inflow"].fillna(0))

    purpose = cur[["area_code", "purpose", "purpose_store_count", "purpose_store_share", "purpose_sales_amount",
                   "purpose_supply_score", "path_v0_score"]].copy()
    if prev is not None:
        lag = prev[["area_code", "purpose", "purpose_sales_amount"]].rename(
            columns={"purpose_sales_amount": "lagged_purpose_sales"})
        purpose = purpose.merge(lag, on=["area_code", "purpose"], how="left")
    else:
        purpose["lagged_purpose_sales"] = np.nan
    return area, purpose


# ---------------------------------------------------------------------------
# R, U, 관성 기준선
# ---------------------------------------------------------------------------

def structural_matrix(area: pd.DataFrame) -> np.ndarray:
    """상권 구조 + 이동 저항. 접근률은 관측 프록시(유입×접근률)와 같은 로그 척도로도 넣는다.
    선형항만 넣으면 접근률 낮은 유명 상권이 가짜 '저유입' 잔차로 잡힌다(자체 검토 1회차)."""
    area = area.assign(log_access=np.log(area["mean_period_ratio"].clip(lower=0.01)))
    cols = ["log_store_total", "log_area_m2", "industry_entropy", "dist_km", "mean_period_ratio", "log_access"]
    cols += [c for c in area.columns if c.startswith("share_")]
    X = area[cols].fillna(0).to_numpy(dtype=float)
    types = np.column_stack([(area["area_type_name"] == t).astype(float) for t in AREA_TYPES[1:]])
    return np.c_[X, types]


def add_inflow_residual(area: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """관측 유입 - 구조 기대 유입(교차적합 Ridge). 음수일수록 '덜 알려짐'."""
    out = area.copy()
    X = structural_matrix(out)
    y = out["log_observed"].to_numpy(dtype=float)
    out["expected_log_observed"] = ridge_oof(X, y, area_folds(out["area_code"], cfg.n_folds), cfg.ridge_alpha)
    resid = y - out["expected_log_observed"]
    out["inflow_residual_z"] = (resid - resid.mean()) / (resid.std() or 1.0)
    out["u_resid"] = pct_rank(-out["inflow_residual_z"])
    out["u_novelty"] = pct_rank(-out["lagged_total_sales"].fillna(0))
    return out


def add_relevance(area: pd.DataFrame, purpose: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """목적별 R ∈ [0,1]."""
    frames = []
    for pur, grp in purpose.groupby("purpose", sort=False):
        g = grp.merge(area, on="area_code", how="inner").copy()
        if g["purpose_sales_amount"].fillna(0).gt(0).sum() >= 30:
            X = np.c_[structural_matrix(g), np.log1p(g["purpose_store_count"].fillna(0)),
                      g["purpose_store_share"].fillna(0)]
            y = np.log1p(g["purpose_sales_amount"].fillna(0).to_numpy(dtype=float))
            g["predicted_purpose_demand"] = ridge_oof(X, y, area_folds(g["area_code"], cfg.n_folds), cfg.ridge_alpha)
            g["relevance_source"] = "목적 매출 Ridge 교차적합 예측"
        else:
            g["predicted_purpose_demand"] = g["purpose_supply_score"]
            g["relevance_source"] = "PATH-v0 공급 점수(매출 원천 없음)"
        g["r_attract"] = pct_rank(g["predicted_purpose_demand"])
        g["r_access"] = pct_rank(g["mean_period_ratio"])
        g["relevance"] = pct_rank((1 - cfg.w_access) * g["r_attract"] + cfg.w_access * g["r_access"])
        frames.append(g)
    return pd.concat(frames, ignore_index=True)


def inertia_rankings(g: pd.DataFrame) -> dict[str, list[str]]:
    """같은 후보군 안에서 세 관성 기준선의 순위 목록."""
    pop = g["lagged_purpose_sales"].fillna(0)
    if pop.sum() == 0:
        pop = g["purpose_store_count"].fillna(0)
    order = {
        "distance": g.assign(_k=g["dist_km"]).sort_values(["_k", "area_code"]),
        "popularity": g.assign(_k=pop).sort_values(["_k", "area_code"], ascending=[False, True]),
        "past_inflow": g.assign(_k=g["observed_inflow"].fillna(0)).sort_values(["_k", "area_code"],
                                                                            ascending=[False, True]),
    }
    return {k: v["area_code"].tolist() for k, v in order.items()}


def category_vectors(g: pd.DataFrame) -> np.ndarray:
    shares = g[[c for c in g.columns if c.startswith("share_")]].fillna(0).to_numpy(dtype=float)
    types = np.column_stack([(g["area_type_name"] == t).astype(float) * 0.5 for t in AREA_TYPES])
    v = np.c_[shares / (shares.max(0, keepdims=True) + 1e-12), types]
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)


def add_unexpectedness(g: pd.DataFrame, inertia_codes: set[str], cfg: Config) -> pd.DataFrame:
    g = g.copy()
    vec = category_vectors(g)
    mask = g["area_code"].isin(inertia_codes).to_numpy()
    cos = vec @ vec[mask].T
    g["cat_distance"] = 1 - cos.max(axis=1)
    d = haversine_km(g["lat"].to_numpy()[:, None], g["lon"].to_numpy()[:, None],
                     g["lat"].to_numpy()[mask][None, :], g["lon"].to_numpy()[mask][None, :])
    g["spatial_distance_km"] = d.min(axis=1)
    g["u_cat"] = pct_rank(g["cat_distance"])
    g["u_spatial"] = pct_rank(g["spatial_distance_km"])
    g["unexpectedness"] = (cfg.w_resid * g["u_resid"] + cfg.w_novelty * g["u_novelty"]
                           + cfg.w_cat * g["u_cat"] + cfg.w_spatial * g["u_spatial"])
    g["in_inertia_topk"] = mask
    return g


def mmr_rerank(g: pd.DataFrame, score_col: str, k: int, lam: float, scale_km: float) -> list[int]:
    """Maximal Marginal Relevance. 반환은 g의 위치 인덱스 목록."""
    elig = np.flatnonzero(g[score_col].notna().to_numpy())
    if elig.size == 0:
        return []
    s = g[score_col].to_numpy(dtype=float)
    s = s / (np.nanmax(s) or 1.0)
    vec = category_vectors(g)
    lat, lon = g["lat"].to_numpy(), g["lon"].to_numpy()
    chosen: list[int] = []
    pool = list(elig)
    while pool and len(chosen) < k:
        if chosen:
            cat = vec[pool] @ vec[chosen].T
            dist = haversine_km(lat[pool][:, None], lon[pool][:, None], lat[chosen][None, :], lon[chosen][None, :])
            sim = (0.5 * cat + 0.5 * np.exp(-dist / scale_km)).max(axis=1)
        else:
            sim = np.zeros(len(pool))
        val = lam * s[pool] - (1 - lam) * sim
        best = pool[int(np.argmax(val))]
        chosen.append(best)
        pool.remove(best)
    return chosen


# ---------------------------------------------------------------------------
# 전체 파이프라인
# ---------------------------------------------------------------------------

def build_serendipity(area: pd.DataFrame, purpose: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(전체 후보 점수표, 기준선 Top-K 표)."""
    area = add_inflow_residual(area, cfg)
    rel = add_relevance(area, purpose, cfg)
    out, base_rows = [], []
    for pur, g in rel.groupby("purpose", sort=False):
        g = g.reset_index(drop=True)
        ranks = inertia_rankings(g)
        inertia = set().union(*(set(v[:cfg.top_k]) for v in ranks.values()))
        for name, codes in ranks.items():
            for i, c in enumerate(codes[:cfg.top_k], 1):
                base_rows.append({"purpose": pur, "baseline": name, "rank": i, "area_code": c})
        g = add_unexpectedness(g, inertia, cfg)
        g["serendipity_score"] = combine_scores(g["relevance"], g["unexpectedness"], cfg.r_floor)
        g["eligible"] = g["serendipity_score"].notna()
        g["score_rank"] = g["serendipity_score"].rank(ascending=False, method="first")
        order = mmr_rerank(g, "serendipity_score", cfg.top_k * 2, cfg.mmr_lambda, cfg.spatial_scale_km)
        g["mmr_rank"] = np.nan
        g.loc[order, "mmr_rank"] = np.arange(1, len(order) + 1)
        g["reason"] = g.apply(reason_text, axis=1)
        out.append(g)
    full = pd.concat(out, ignore_index=True)
    names = area.set_index("area_code")[["area_name", "primary_district_name", "dist_km"]]
    base = pd.DataFrame(base_rows).join(names, on="area_code")
    return full, base


def reason_text(r: pd.Series) -> str:
    if not r.get("eligible", False):
        return "관련성 하한 미달로 제외"
    parts = []
    if r["u_resid"] >= 0.7:
        parts.append("구조 대비 유입이 적음")
    if r["u_novelty"] >= 0.6:
        parts.append("도시 전체 인기 하위권")
    if r["u_cat"] >= 0.7:
        parts.append("관성 상위권과 업종 구성이 다름")
    if r["u_spatial"] >= 0.7:
        parts.append(f"관성 상위권에서 {r['spatial_distance_km']:.1f}km 떨어짐")
    if r["relevance"] >= 0.85:
        parts.append("목적 매력도 상위")
    return " · ".join(parts) or "관련성·의외성 균형"


OUT_COLS = ["purpose", "mmr_rank", "score_rank", "area_code", "area_name", "primary_district_name", "area_type_name",
            "serendipity_score", "relevance", "unexpectedness", "u_resid", "u_novelty", "u_cat", "u_spatial",
            "r_attract", "r_access", "relevance_source", "inflow_residual_z", "cat_distance", "spatial_distance_km",
            "dist_km", "mean_period_ratio", "observed_inflow", "lagged_total_sales", "lagged_purpose_sales", "path_v0_score",
            "in_inertia_topk", "eligible", "reason"]


def top_list(full: pd.DataFrame, pur: str, k: int) -> list[str]:
    g = full[(full["purpose"] == pur) & full["mmr_rank"].notna()].sort_values("mmr_rank")
    return g["area_code"].head(k).tolist()


# ---------------------------------------------------------------------------
# 평가: beyond-accuracy, 백테스트, 민감도, 반사실
# ---------------------------------------------------------------------------

def beyond_accuracy(full: pd.DataFrame, base: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    k = cfg.top_k
    rows = []
    n_cand = full["area_code"].nunique()
    lists: dict[str, dict[str, list[str]]] = {"serendipity": {}, **{b: {} for b in BASELINES}}
    for pur in full["purpose"].unique():
        lists["serendipity"][pur] = top_list(full, pur, k)
        for b in BASELINES:
            lists[b][pur] = base[(base["purpose"] == pur) & (base["baseline"] == b)].sort_values("rank")["area_code"].tolist()
    for method, by_pur in lists.items():
        exposure = pd.Series(0, index=full["area_code"].unique(), dtype=float)
        for pur, codes in by_pur.items():
            g = full[full["purpose"] == pur].reset_index(drop=True)
            pos = pd.Series(g.index, index=g["area_code"])
            sel = g.set_index("area_code").loc[codes]
            inertia = set(base[base["purpose"] == pur]["area_code"])
            vec = category_vectors(g)[pos[codes].to_numpy()]  # 후보 전체 기준 정규화(방법 간 같은 척도)
            ild = 1 - (vec @ vec.T)[np.triu_indices(len(codes), 1)].mean() if len(codes) > 1 else 0.0
            exposure[codes] += 1
            rows.append({
                "method": method, "purpose": pur, "k": len(codes),
                "mean_relevance": sel["relevance"].mean(),
                "share_below_r_floor": (sel["relevance"] < cfg.r_floor).mean(),
                "mean_u_resid": sel["u_resid"].mean(),
                "mean_u_novelty": sel["u_novelty"].mean(),
                "overlap_inertia_union": len(set(codes) & inertia) / k,
                **{f"overlap_{b}": overlap_at_k(codes, lists[b][pur], k) for b in BASELINES},
                "distinct_districts": sel["primary_district_name"].nunique(),
                "distinct_area_types": sel["area_type_name"].nunique(),
                "intra_list_diversity": ild,
                "mean_dist_km": sel["dist_km"].mean(),
                "mean_access_ratio": sel["mean_period_ratio"].mean(),
            })
        rows.append({"method": method, "purpose": "_전체", "k": k,
                     "catalog_coverage": (exposure > 0).sum() / n_cand,
                     "exposure_gini": gini(exposure.to_numpy())})
    return pd.DataFrame(rows)


def ndcg_at_k(ranked: list[str], positives: set[str], k: int) -> float:
    dcg = sum(1 / np.log2(i + 2) for i, c in enumerate(ranked[:k]) if c in positives)
    idcg = sum(1 / np.log2(i + 2) for i in range(min(k, len(positives))))
    return dcg / idcg if idcg else np.nan


def proxy_labels(root: Path, as_of: int, future: int, pop_q: float = 0.5, growth_q: float = 0.8) -> pd.DataFrame:
    """사후 세렌디피티 프록시 라벨.

    as-of 분기에 목적 매출이 하위 pop_q 이하(덜 알려짐)였는데 future 분기까지 목적 매출 로그 증가가
    목적 안 상위 (1-growth_q)에 든 상권 = 1.
    """
    qf = pd.read_csv(root / "data/processed/commercial_area_purpose_features/official_area_purpose_quarter_features.csv",
                     dtype={"area_code": str})
    a = qf[qf["quarter"] == as_of][["area_code", "purpose", "purpose_sales_amount"]]
    b = qf[qf["quarter"] == future][["area_code", "purpose", "purpose_sales_amount"]]
    m = a.merge(b, on=["area_code", "purpose"], suffixes=("_t", "_f"))
    m["growth"] = np.log1p(m["purpose_sales_amount_f"]) - np.log1p(m["purpose_sales_amount_t"])
    out = []
    for pur, g in m.groupby("purpose"):
        if g["purpose_sales_amount_f"].gt(0).sum() < 30:
            continue
        low = g["purpose_sales_amount_t"] <= g["purpose_sales_amount_t"].quantile(pop_q)
        grew = (g["growth"] >= g["growth"].quantile(growth_q)) & (g["purpose_sales_amount_f"] > 0)
        g = g.assign(label=(low & grew).astype(int))
        out.append(g)
    return pd.concat(out, ignore_index=True)


def backtest(root: Path, cfg: Config, as_of: int = 20252, future: int = 20254) -> pd.DataFrame:
    area, purpose = load_inputs(root, as_of, use_movement=False)
    full, base = build_serendipity(area, purpose, cfg)
    labels = proxy_labels(root, as_of, future)
    k = cfg.top_k
    rows = []
    rng = np.random.default_rng(0)
    for pur, lab in labels.groupby("purpose"):
        pos = set(lab.loc[lab["label"] == 1, "area_code"])
        g = full[full["purpose"] == pur]
        lists = {
            "serendipity_mmr": top_list(full, pur, k),
            "serendipity_score_only": g.sort_values("score_rank")["area_code"].head(k).tolist(),
            "residual_only": g.sort_values("u_resid", ascending=False)["area_code"].head(k).tolist(),
            "path_v0": g.sort_values("path_v0_score", ascending=False)["area_code"].head(k).tolist(),
            **{b: base[(base["purpose"] == pur) & (base["baseline"] == b)].sort_values("rank")["area_code"].tolist()
               for b in BASELINES},
        }
        pos_r = g[g["area_code"].isin(pos)]["relevance"]
        codes = g["area_code"].to_numpy()
        rand = [len(set(rng.choice(codes, k, replace=False)) & pos) / k for _ in range(500)]
        for m, lst in lists.items():
            rows.append({"as_of": as_of, "future": future, "purpose": pur, "method": m,
                         "positives": len(pos), "candidates": len(codes),
                         f"precision_at_{k}": len(set(lst[:k]) & pos) / k,
                         f"recall_at_{k}": len(set(lst[:k]) & pos) / max(len(pos), 1),
                         f"ndcg_at_{k}": ndcg_at_k(lst, pos, k),
                         "random_precision_mean": float(np.mean(rand)),
                         "positives_passing_r_floor": float((pos_r >= cfg.r_floor).mean()) if len(pos_r) else np.nan})
    return pd.DataFrame(rows)


def sensitivity(area: pd.DataFrame, purpose: pd.DataFrame, cfg: Config, ref: pd.DataFrame) -> pd.DataFrame:
    variants = {
        "r_floor=0.5": dict(r_floor=0.5), "r_floor=0.7": dict(r_floor=0.7), "r_floor=0.8": dict(r_floor=0.8),
        "lambda=0.5": dict(mmr_lambda=0.5), "lambda=0.9": dict(mmr_lambda=0.9), "lambda=1.0(MMR 끔)": dict(mmr_lambda=1.0),
        "U=잔차만": dict(w_resid=1.0, w_novelty=0.0, w_cat=0.0, w_spatial=0.0),
        "U=새로움 제외(과제 원정의)": dict(w_resid=0.5, w_novelty=0.0, w_cat=0.25, w_spatial=0.25),
        "U=균등": dict(w_resid=0.25, w_novelty=0.25, w_cat=0.25, w_spatial=0.25),
        "U=거리만": dict(w_resid=0.0, w_novelty=0.0, w_cat=0.5, w_spatial=0.5),
        "K=5": dict(top_k=5),
    }
    rows = []
    for name, kw in variants.items():
        c = Config(**{**cfg.__dict__, **kw})
        full, base = build_serendipity(area, purpose, c)
        for pur in ref["purpose"].unique():
            a, b = top_list(ref, pur, c.top_k), top_list(full, pur, c.top_k)
            inertia = set(base[base["purpose"] == pur]["area_code"])
            rel = full[full["purpose"] == pur].set_index("area_code")["relevance"]
            rows.append({"variant": name, "purpose": pur,
                         "jaccard_vs_default_topk": len(set(a) & set(b)) / max(len(set(a) | set(b)), 1),
                         "overlap_inertia_union": len(set(b) & inertia) / c.top_k,
                         "mean_relevance": rel.reindex(b).mean() if b else np.nan})
    return pd.DataFrame(rows)


def counterfactual(full: pd.DataFrame, base: pd.DataFrame, cfg: Config, shares=(0.05, 0.1, 0.2)) -> pd.DataFrame:
    """Mauro 등(2025) 식 반사실: 동대문구발 비일상 유입 중 일부가 추천 Top-K로 옮겨갈 때
    도시 전체(후보 786곳) 유입 지니가 어떻게 변하는가. 옮겨가는 유입은 기존 분포에서 비례 차감하고
    추천 목록 순위 가중(1/log2(rank+1))으로 배분한다. 행동 반응 모형이 아니라 산술 시뮬레이션이다."""
    area = full.drop_duplicates("area_code").set_index("area_code")["observed_inflow"].fillna(0)
    total = area.sum()
    rows = [{"method": "현재(관측 프록시)", "moved_share": 0.0, "inflow_gini": gini(area), "top10pct_share":
             area.sort_values(ascending=False).head(len(area) // 10).sum() / total}]
    methods = {"serendipity": lambda p: top_list(full, p, cfg.top_k)}
    for b in BASELINES:
        methods[b] = lambda p, b=b: base[(base["purpose"] == p) & (base["baseline"] == b)].sort_values("rank")["area_code"].tolist()
    purposes = [p for p in full["purpose"].unique()]
    for m, fn in methods.items():
        for s in shares:
            alloc = pd.Series(0.0, index=area.index)
            for p in purposes:
                codes = fn(p)
                w = 1 / np.log2(np.arange(1, len(codes) + 1) + 1)
                alloc[codes] += w / w.sum() / len(purposes)
            new = area * (1 - s) + total * s * alloc
            rows.append({"method": m, "moved_share": s, "inflow_gini": gini(new),
                         "top10pct_share": new.sort_values(ascending=False).head(len(new) // 10).sum() / total})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    root = Path(args.root)
    cfg = Config(top_k=args.top_k, r_floor=args.r_floor, mmr_lambda=args.mmr_lambda)
    area, purpose = load_inputs(root, args.quarter, use_movement=True)
    full, base = build_serendipity(area, purpose, cfg)
    out = root / args.output
    out.mkdir(parents=True, exist_ok=True)
    full = full.sort_values(["purpose", "mmr_rank", "score_rank"], na_position="last")
    full[OUT_COLS].to_csv(out / "serendipity_ranking_latest.csv", index=False, encoding="utf-8-sig")
    full[full["mmr_rank"] <= cfg.top_k][OUT_COLS].to_csv(out / "serendipity_top10_by_purpose.csv",
                                                           index=False, encoding="utf-8-sig")
    base.to_csv(out / "inertia_baselines_top10.csv", index=False, encoding="utf-8-sig")
    metrics = beyond_accuracy(full, base, cfg)
    metrics.to_csv(out / "serendipity_beyond_accuracy.csv", index=False, encoding="utf-8-sig")
    bt = backtest(root, cfg)
    bt.to_csv(out / "serendipity_backtest_proxy_label.csv", index=False, encoding="utf-8-sig")
    sens = sensitivity(area, purpose, cfg, full)
    sens.to_csv(out / "serendipity_sensitivity.csv", index=False, encoding="utf-8-sig")
    cf = counterfactual(full, base, cfg)
    cf.to_csv(out / "serendipity_counterfactual.csv", index=False, encoding="utf-8-sig")
    summary = {
        "quarter": args.quarter, "candidates": int(full["area_code"].nunique()),
        "config": {k: v for k, v in cfg.__dict__.items()},
        "eligible_per_purpose": full.groupby("purpose")["eligible"].sum().astype(int).to_dict(),
        "observed_inflow_source": str(area["observed_source"].iloc[0]),
    }
    (out / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote serendipity ranking: {len(full):,} rows, top-{cfg.top_k} for {full['purpose'].nunique()} purposes")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=Path(__file__).resolve().parents[1])
    ap.add_argument("--quarter", type=int, default=20254)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--r-floor", type=float, default=0.6)
    ap.add_argument("--mmr-lambda", type=float, default=0.7)
    ap.add_argument("--output", default="data/processed/serendipity_ranking")
    return ap.parse_args()


if __name__ == "__main__":
    run(parse_args())
