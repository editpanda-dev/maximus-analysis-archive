"""접근성 기준(25% / 50% / 80%) 민감도 분석.

세 시간대(08, 14, 19시) 모두 기준 이상인 공식 상권만 후보로 남기고,
기존 PATH-v0 순위 로직(build_commercial_area_purpose_features.build_features)을
후보군만 바꿔 그대로 재실행해서 후보군·목적별 top 10이 얼마나 유지되는지 계산한다.

기존 스크립트는 수정하지 않고 import해서 재사용한다.

실행:
    python scripts/analyze_accessibility_sensitivity.py
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import pandas as pd

THRESHOLDS = (0.25, 0.50, 0.80)
PERIOD_COLS = ("ratio_08", "ratio_14", "ratio_19")
CORE_PURPOSES = ("식사", "카페", "쇼핑", "여가문화")
STUDY_PURPOSE = "공부"  # 2026-09-18 POI 스냅샷 계열이라 본 결과와 분리 표기
TOP_N = 10

BOUNDARY_COLS = [
    "area_code", "area_name", "area_type_name", "primary_admin_name", "primary_district_name",
    "ratio_08", "ratio_14", "ratio_19", "minimum_period_ratio", "access_tier",
]


def pct_label(threshold: float) -> str:
    return f"{int(round(threshold * 100))}pct"


def filter_candidates(candidates: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """세 시간대 접근 비율이 모두 threshold 이상인 상권만 남긴다."""
    ok = (candidates[list(PERIOD_COLS)] >= threshold).all(axis=1)
    return candidates.loc[ok].copy()


def jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else float("nan")


def top_areas(ranked: pd.DataFrame, purpose: str, n: int = TOP_N) -> set:
    """purpose_rank <= n 인 상권 코드 집합 (동점이면 n개보다 많을 수 있음)."""
    sub = ranked[(ranked["purpose"] == purpose) & (ranked["purpose_rank"] <= n)]
    return set(sub["area_code"].astype(str))


def boundary_candidates(candidates: pd.DataFrame, top_by_purpose_25: dict) -> pd.DataFrame:
    """25%에는 포함되지만 50% 또는 80%에서 빠지는 상권."""
    df = candidates.copy()
    df["area_code"] = df["area_code"].astype(str)
    df["in_50pct"] = (df[list(PERIOD_COLS)] >= 0.50).all(axis=1)
    df["in_80pct"] = (df[list(PERIOD_COLS)] >= 0.80).all(axis=1)
    out = df[~(df["in_50pct"] & df["in_80pct"])].copy()
    # 50%에서 빠지면 80%에서도 빠진다. 50%를 통과하고 80%만 못 넘으면 '80pct'
    out["first_dropped_at"] = out["in_50pct"].map({True: "80pct", False: "50pct"})
    core_hits = {
        code: [p for p in CORE_PURPOSES if code in top_by_purpose_25.get(p, set())]
        for code in out["area_code"]
    }
    out["top10_purposes_at_25pct"] = out["area_code"].map(lambda c: ",".join(core_hits[c]))
    out["study_top10_at_25pct"] = out["area_code"].map(lambda c: c in top_by_purpose_25.get(STUDY_PURPOSE, set()))
    cols = [c for c in BOUNDARY_COLS if c in out.columns] + [
        "in_50pct", "in_80pct", "first_dropped_at", "top10_purposes_at_25pct", "study_top10_at_25pct",
    ]
    return out[cols].sort_values(["first_dropped_at", "minimum_period_ratio", "area_code"]).reset_index(drop=True)


def stability_rows(rankings: dict, cand_sets: dict, n: int = TOP_N) -> pd.DataFrame:
    """목적별, 기준 쌍별 top 10 유지율.

    overlap_*  : 각 기준에서 후보군만 바꿔 순위를 재계산한 top 10끼리 비교 (정규화 변화 포함)
    retained_* : a 기준 top 10 중 더 엄격한 b 기준 후보군에 남아 있는 비율 (순위 재계산 없음)
    """
    rows = []
    groups = {"core4": CORE_PURPOSES, "study_separate": (STUDY_PURPOSE,)}
    for group, purposes in groups.items():
        for purpose in purposes:
            tops = {t: top_areas(rankings[t], purpose, n) for t in THRESHOLDS}
            for a, b in itertools.combinations(THRESHOLDS, 2):
                ta, tb = tops[a], tops[b]
                inter = ta & tb
                denom = min(len(ta), len(tb))
                kept = ta & cand_sets[b]
                rows.append({
                    "group": group,
                    "purpose": purpose,
                    "threshold_a": pct_label(a),
                    "threshold_b": pct_label(b),
                    "n_top_a": len(ta),
                    "n_top_b": len(tb),
                    "overlap_count": len(inter),
                    "overlap_ratio": len(inter) / denom if denom else float("nan"),
                    "jaccard": jaccard(ta, tb),
                    "retained_in_b_candidates": len(kept),
                    "retained_ratio": len(kept) / len(ta) if ta else float("nan"),
                })
    return pd.DataFrame(rows)


def membership_rows(rankings: dict, n: int = TOP_N) -> pd.DataFrame:
    """기준별 top 10 목록 (area_code 기준으로 통합할 때 쓰는 long 형식)."""
    frames = []
    for t in THRESHOLDS:
        r = rankings[t]
        sub = r[r["purpose_rank"] <= n].copy()
        sub["threshold"] = pct_label(t)
        sub["group"] = sub["purpose"].map(lambda p: "study_separate" if p == STUDY_PURPOSE else "core4")
        frames.append(sub)
    out = pd.concat(frames, ignore_index=True)
    cols = ["threshold", "group", "purpose", "purpose_rank", "area_code", "area_name", "path_v0_score"]
    return out[[c for c in cols if c in out.columns]].sort_values(
        ["group", "purpose", "threshold", "purpose_rank", "area_code"]
    ).reset_index(drop=True)


def threshold_summary(cand_sets: dict, stability: pd.DataFrame) -> pd.DataFrame:
    """후보 수, 교집합, top 10 유지율을 표 하나로."""
    core = stability[stability["group"] == "core4"]
    base = cand_sets[0.25]
    rows = []
    for t in THRESHOLDS:
        row = {
            "threshold": pct_label(t),
            "periods_required": "ratio_08,ratio_14,ratio_19 모두 기준 이상",
            "n_candidates": len(cand_sets[t]),
            "share_of_25pct_candidates": len(cand_sets[t]) / len(base),
        }
        for u in THRESHOLDS:
            row[f"intersection_with_{pct_label(u)}"] = len(cand_sets[t] & cand_sets[u])
            row[f"candidate_jaccard_vs_{pct_label(u)}"] = jaccard(cand_sets[t], cand_sets[u])
        if t == 0.25:
            row["core4_mean_top10_overlap_vs_25pct"] = 1.0
            row["core4_mean_top10_retained_vs_25pct"] = 1.0
        else:
            sel = core[(core["threshold_a"] == "25pct") & (core["threshold_b"] == pct_label(t))]
            row["core4_mean_top10_overlap_vs_25pct"] = sel["overlap_ratio"].mean()
            row["core4_mean_top10_retained_vs_25pct"] = sel["retained_ratio"].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def recompute_rankings(stores, sales, candidates: pd.DataFrame) -> pd.DataFrame:
    """기존 PATH-v0 로직을 그대로 재사용해 최신 분기 순위를 다시 계산한다."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_commercial_area_purpose_features as bcp

    feats = bcp.build_features(stores, sales, candidates)
    latest_q = feats["quarter"].max()
    latest = feats[(feats["quarter"] == latest_q) & feats["path_v0_score"].notna()].copy()
    latest["area_code"] = latest["area_code"].astype(str)
    return latest


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_commercial_area_purpose_features as bcp

    parser = argparse.ArgumentParser()
    parser.add_argument("--stores", type=Path, default=Path("data/raw/commercial_area/commercial_store_2025.zip"))
    parser.add_argument("--sales", type=Path, default=Path("data/raw/commercial_area/commercial_sales_2025.zip"))
    parser.add_argument("--candidates", type=Path,
                        default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv"))
    parser.add_argument("--existing-rankings", type=Path,
                        default=Path("data/processed/commercial_area_purpose_features/official_area_purpose_latest_rankings.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/accessibility_sensitivity"))
    args = parser.parse_args()

    candidates = pd.read_csv(args.candidates, dtype={"area_code": str})
    stores = bcp.read_zip_csv(args.stores)
    sales = bcp.read_zip_csv(args.sales)

    # 1) 기준별 후보군 + 세 시간대 조건 검증
    cand_frames = {t: filter_candidates(candidates, t) for t in THRESHOLDS}
    cand_sets = {t: set(f["area_code"].astype(str)) for t, f in cand_frames.items()}
    for t in THRESHOLDS:
        by_min = int((candidates["minimum_period_ratio"] >= t).sum())
        assert len(cand_sets[t]) == by_min, f"{pct_label(t)}: 세 시간대 필터({len(cand_sets[t])})와 minimum_period_ratio({by_min}) 불일치"
        print(f"[후보] {pct_label(t)}: {len(cand_sets[t])}개")
    assert len(cand_sets[0.25]) == len(candidates), "25% 후보가 원본 후보 파일 행 수와 다릅니다"

    # 2) 기준별 순위 재계산 (기존 로직 재사용)
    rankings = {t: recompute_rankings(stores, sales, cand_frames[t]) for t in THRESHOLDS}

    # 3) 25% 재계산이 기존 순위 파일과 같은지 확인
    if args.existing_rankings.exists():
        old = pd.read_csv(args.existing_rankings, dtype={"area_code": str})
        for purpose in list(CORE_PURPOSES) + [STUDY_PURPOSE]:
            old_top = set(old[(old["purpose"] == purpose) & (old["purpose_rank"] <= TOP_N)]["area_code"])
            new_top = top_areas(rankings[0.25], purpose)
            flag = "OK" if old_top == new_top else "불일치!"
            print(f"[재현 확인] {purpose}: {flag} (기존 {len(old_top)}개 / 재계산 {len(new_top)}개)")

    # 4) 결과표
    stability = stability_rows(rankings, cand_sets)
    summary = threshold_summary(cand_sets, stability)
    top25 = {p: top_areas(rankings[0.25], p) for p in list(CORE_PURPOSES) + [STUDY_PURPOSE]}
    boundary = boundary_candidates(cand_frames[0.25], top25)
    membership = membership_rows(rankings)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "threshold_summary.csv": summary,
        "purpose_top10_stability.csv": stability,
        "boundary_candidate_areas.csv": boundary,
        "top10_membership_by_threshold.csv": membership,
    }
    for name, df in outputs.items():
        df.to_csv(args.output_dir / name, index=False, encoding="utf-8-sig")
        print(f"[저장] {args.output_dir / name} ({len(df)}행)")

    print("\n=== threshold_summary ===")
    print(summary.to_string(index=False))
    print("\n=== purpose_top10_stability (core4) ===")
    print(stability[stability["group"] == "core4"].to_string(index=False))


if __name__ == "__main__":
    main()
