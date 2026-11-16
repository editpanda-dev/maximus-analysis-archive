#!/usr/bin/env python3
"""Elastic Net 1차 실험 v0.

의외성 랭킹(SERP-v0)의 두 회귀를 Elastic Net으로 바꿔 본다.
  1) 유입 모형  log(관측 유입) ~ 상권 구조   → 잔차가 U의 `u_resid`("구조에 비해 덜 간다")
  2) 목적 매출 모형  log(목적 매출) ~ 상권 구조 → 예측값이 R의 `r_attract`("구조로 기대되는 매력")

보는 것
  - 성능: 상권 무작위 5겹 / 자치구 묶음 5겹에서 OLS·현행 Ridge(α=1)·RidgeCV·LassoCV·ENCV·HistGB 비교
  - 변수: EN 표준화 계수, 부트스트랩 200회 선택 빈도·부호 일관성
  - 랭킹 영향: 현행 Ridge 대비 잔차·예측 순위 상관, 상위 50 겹침

실행: 저장소 루트 아닌 프로젝트 폴더에서
  ~/.venvs/maximus/bin/python 분석/elastic_net_v0.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet, ElasticNetCV, LassoCV, LinearRegression, Ridge, RidgeCV
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)

HERE = Path(__file__).resolve().parents[1]
REPO = HERE / "maximus-analysis-archive"
sys.path.insert(0, str(REPO / "scripts"))
from build_serendipity_ranking import AREA_TYPES, load_inputs  # noqa: E402

OUT = HERE / "데이터/가공/elastic_net"
QUARTER = 20254
L1_GRID = [0.1, 0.3, 0.5, 0.7, 0.9, 0.95, 1.0]
N_BOOT = 200
SEED = 0


# ---------------------------------------------------------------------------
# 피처
# ---------------------------------------------------------------------------

def base_features(area: pd.DataFrame) -> pd.DataFrame:
    """현행 structural_matrix와 같은 열(이름 붙임)."""
    X = pd.DataFrame(index=area.index)
    X["log_점포수"] = area["log_store_total"]
    X["log_면적"] = area["log_area_m2"]
    X["업종엔트로피"] = area["industry_entropy"]
    X["동대문거리_km"] = area["dist_km"]
    X["30분도달률"] = area["mean_period_ratio"]
    X["log_도달률"] = np.log(area["mean_period_ratio"].clip(lower=0.01))
    for c in [c for c in area.columns if c.startswith("share_")]:
        X["비중_" + c[6:]] = area[c]
    for t in AREA_TYPES[1:]:
        X["유형_" + t] = (area["area_type_name"] == t).astype(float)
    return X.fillna(0)


def extra_features(area: pd.DataFrame) -> pd.DataFrame:
    """확장: 시간대 도달률, 공공 태그(노포·10년+·오래된카페·착한가격). 리뷰는 식사에서만 따로."""
    qf = pd.read_csv(REPO / "data/processed/commercial_area_purpose_features/official_area_purpose_quarter_features.csv",
                     dtype={"area_code": str})
    tf = qf[qf["quarter"] == QUARTER].drop_duplicates("area_code")[["area_code", "ratio_08", "ratio_14", "ratio_19"]]
    tags = pd.read_csv(HERE / "데이터/가공/서울캠/seoulcampus_area_tags_v1.csv", dtype={"area_code": str})
    a = area[["area_code"]].merge(tf, on="area_code", how="left").merge(
        tags[["area_code", "n_nopo", "n_10yr", "n_old_cafe", "n_goodprice"]], on="area_code", how="left")
    X = pd.DataFrame(index=area.index)
    X["도달률_08시"] = a["ratio_08"].to_numpy()
    X["도달률_14시"] = a["ratio_14"].to_numpy()
    X["도달률_19시"] = a["ratio_19"].to_numpy()
    for c, k in [("n_nopo", "노포"), ("n_10yr", "10년+"), ("n_old_cafe", "오래된카페"), ("n_goodprice", "착한가격")]:
        X["log_" + k] = np.log1p(a[c].fillna(0).to_numpy())
    return X.fillna(X.median())


def review_features(area: pd.DataFrame) -> pd.DataFrame:
    rv = pd.read_csv(HERE / "데이터/가공/naver_reviews/area_dining_review_summary.csv", dtype={"area_code": str})
    a = area[["area_code"]].merge(rv, on="area_code", how="left")
    X = pd.DataFrame(index=area.index)
    X["log_리뷰수중앙값"] = np.log1p(a["naver_review_total_median"]).to_numpy()
    X["평균평점"] = a["mean_rating_2026"].to_numpy()
    X["리뷰_결측"] = X["log_리뷰수중앙값"].isna().astype(float)
    return X.fillna(X.median())


# ---------------------------------------------------------------------------
# 모형
# ---------------------------------------------------------------------------

def models() -> dict:
    inner = KFold(5, shuffle=True, random_state=SEED)
    return {
        "OLS": make_pipeline(StandardScaler(), LinearRegression()),
        "Ridge(α=1, 현행)": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "RidgeCV": make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 50))),
        "LassoCV": make_pipeline(StandardScaler(), LassoCV(cv=inner, alphas=60, max_iter=20000)),
        "ElasticNetCV": make_pipeline(StandardScaler(), ElasticNetCV(l1_ratio=L1_GRID, cv=inner, alphas=60,
                                                                     max_iter=20000)),
        "HistGB(비교)": HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=SEED),
    }


def oof(model, X: np.ndarray, y: np.ndarray, splits) -> np.ndarray:
    pred = np.zeros_like(y)
    for tr, te in splits:
        pred[te] = model.fit(X[tr], y[tr]).predict(X[te])
    return pred


def r2(y, p) -> float:
    return float(1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def evaluate(name: str, X: pd.DataFrame, y: np.ndarray, area: pd.DataFrame) -> tuple[list, dict]:
    Xn = X.to_numpy(float)
    rand = list(KFold(5, shuffle=True, random_state=SEED).split(Xn))
    grp = list(GroupKFold(5).split(Xn, groups=area["primary_district_name"].fillna("미상")))
    rows, preds = [], {}
    for m, est in models().items():
        p_rand = oof(est, Xn, y, rand)
        p_grp = oof(est, Xn, y, grp)
        preds[m] = p_rand
        rows.append({"target": name, "model": m, "r2_random_area": r2(y, p_rand), "r2_district_group": r2(y, p_grp)})
    return rows, preds


def en_fit(X: pd.DataFrame, y: np.ndarray):
    pipe = make_pipeline(StandardScaler(), ElasticNetCV(l1_ratio=L1_GRID, cv=KFold(5, shuffle=True, random_state=SEED),
                                                        alphas=60, max_iter=20000)).fit(X.to_numpy(float), y)
    return pipe[-1]


def stability(X: pd.DataFrame, y: np.ndarray, alpha: float, l1: float) -> pd.DataFrame:
    """고정 (α, l1_ratio)로 부트스트랩 재적합 → 선택 빈도·부호 일관성."""
    rng = np.random.default_rng(SEED)
    Xs = StandardScaler().fit_transform(X.to_numpy(float))
    coefs = np.zeros((N_BOOT, Xs.shape[1]))
    for b in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        coefs[b] = ElasticNet(alpha=alpha, l1_ratio=l1, max_iter=20000).fit(Xs[i], y[i]).coef_
    nz = coefs != 0
    sign = np.sign(np.median(coefs, axis=0))
    return pd.DataFrame({
        "feature": X.columns,
        "select_freq": nz.mean(0),
        "sign_consistency": (np.sign(coefs) == sign).mean(0),
        "coef_median": np.median(coefs, 0),
        "coef_p05": np.percentile(coefs, 5, 0),
        "coef_p95": np.percentile(coefs, 95, 0),
    })


def run_target(name: str, X: pd.DataFrame, y: np.ndarray, area: pd.DataFrame, use_resid: bool):
    perf, preds = evaluate(name, X, y, area)
    en = en_fit(X, y)
    coef = pd.DataFrame({"feature": X.columns, "en_coef_std": en.coef_})
    stab = stability(X, y, en.alpha_, en.l1_ratio_)
    coef = coef.merge(stab, on="feature")
    coef.insert(0, "target", name)
    coef["en_alpha"], coef["en_l1_ratio"] = en.alpha_, en.l1_ratio_
    # 랭킹 영향: 현행 Ridge vs EN (상권 무작위 5겹 OOF)
    cur, new = preds["Ridge(α=1, 현행)"], preds["ElasticNetCV"]
    if use_resid:  # 잔차가 작을수록 '덜 간다'
        s_cur, s_new = y - cur, y - new
        top_cur, top_new = np.argsort(s_cur)[:50], np.argsort(s_new)[:50]
    else:          # 예측값이 클수록 '매력'
        s_cur, s_new = cur, new
        top_cur, top_new = np.argsort(-s_cur)[:50], np.argsort(-s_new)[:50]
    impact = {"target": name, "score": "잔차(저유입)" if use_resid else "예측(매력)",
              "spearman_vs_current": float(spearmanr(s_cur, s_new)[0]),
              "top50_overlap": len(set(top_cur) & set(top_new)) / 50,
              "n_features": X.shape[1], "n_selected": int((en.coef_ != 0).sum()),
              "alpha": en.alpha_, "l1_ratio": en.l1_ratio_}
    return perf, coef, impact, s_new


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    area, purpose = load_inputs(REPO, QUARTER, use_movement=True)
    area = area.reset_index(drop=True)
    Xb, Xe = base_features(area), extra_features(area)
    perf_all, coef_all, impact_all = [], [], []

    def add(res):
        perf_all.extend(res[0]); coef_all.append(res[1]); impact_all.append(res[2])

    # 1) 유입 모형 (U의 엔진)
    # 누수: 현행 타깃 log_observed = log(비일상 유입 × 30분 도달률)이라 도달률 피처가 식 자체를 맞춘다.
    #   (a) 누수 재현: 현행 타깃 + 도달률 피처 포함
    #   (b) 수정안: 타깃을 log(비일상 유입) 원값으로. 도달률은 '접근성이 유입을 늘리나'를 보는 정당한 설명변수
    #   (c) 점검: 현행 타깃 유지 + 도달률 피처 전부 제외
    access_cols = ["30분도달률", "log_도달률", "도달률_08시", "도달률_14시", "도달률_19시"]
    Xbe = pd.concat([Xb, Xe], axis=1)
    y_cur = area["log_observed"].to_numpy(float)
    y_raw = np.log1p(area["inflow_nonroutine"].to_numpy(float))
    variants = [
        ("유입×도달률(누수)|확장", y_cur, Xbe),
        ("유입원값(수정)|기본", y_raw, Xb),
        ("유입원값(수정)|확장", y_raw, Xbe),
        ("유입×도달률|도달률제외", y_cur, Xbe.drop(columns=access_cols)),
    ]
    for name, y, X in variants:
        ok = np.isfinite(y)
        res = run_target(name, X[ok].reset_index(drop=True), y[ok], area[ok].reset_index(drop=True), True)
        add(res)
        if name == "유입원값(수정)|확장":
            resid = area.loc[ok, ["area_code", "area_name", "primary_district_name", "area_type_name",
                                  "inflow_nonroutine", "mean_period_ratio"]].copy()
            resid["en_resid"] = res[3]
            resid.sort_values("en_resid").to_csv(OUT / "inflow_residual_en.csv", index=False, encoding="utf-8-sig")

    # 2) 목적 매출 모형 (R의 엔진). 공부는 매출 원천 없음
    for pur in ["식사", "카페", "쇼핑", "여가문화"]:
        g = purpose[purpose["purpose"] == pur].merge(area[["area_code"]].reset_index(), on="area_code")
        idx = g["index"].to_numpy()
        yp = np.log1p(g["purpose_sales_amount"].fillna(0).to_numpy(float))
        own = pd.DataFrame({"log_목적점포수": np.log1p(g["purpose_store_count"].fillna(0)).to_numpy(),
                            "목적점포비중": g["purpose_store_share"].fillna(0).to_numpy()})
        sets = [("기본", pd.concat([Xb.iloc[idx].reset_index(drop=True), own], axis=1)),
                ("확장", pd.concat([Xb.iloc[idx].reset_index(drop=True), Xe.iloc[idx].reset_index(drop=True), own], axis=1))]
        if pur == "식사":
            sets.append(("확장+리뷰", pd.concat([sets[1][1], review_features(area).iloc[idx].reset_index(drop=True)], axis=1)))
        for tag, X in sets:
            add(run_target(f"{pur}매출|{tag}", X, yp, area.iloc[idx].reset_index(drop=True), False))

    perf = pd.DataFrame(perf_all)
    coef = pd.concat(coef_all, ignore_index=True)
    impact = pd.DataFrame(impact_all)
    perf.to_csv(OUT / "model_comparison.csv", index=False, encoding="utf-8-sig")
    coef.to_csv(OUT / "en_coefficients_stability.csv", index=False, encoding="utf-8-sig")
    impact.to_csv(OUT / "ranking_impact.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200, "display.max_rows", 200)
    print(perf.pivot(index="target", columns="model", values="r2_district_group").round(3))
    print(perf.pivot(index="target", columns="model", values="r2_random_area").round(3))
    print(impact.round(3))
    for t, g in coef.groupby("target", sort=False):
        g = g.reindex(g["en_coef_std"].abs().sort_values(ascending=False).index)
        print(f"\n== {t} (alpha={g.en_alpha.iloc[0]:.4f}, l1={g.en_l1_ratio.iloc[0]})")
        print(g[["feature", "en_coef_std", "select_freq", "sign_consistency"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
