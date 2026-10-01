#!/usr/bin/env python3
"""Create transparent purpose-specific features for reachable Seoul dongs.

The output is deliberately a feature mart, not a final recommendation list.  It
keeps supply (store/facility) and observed consumption separate, and exposes a
one-quarter-lagged consumption signal for use in later prediction models.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:  # Supports both `python -m scripts...` and direct execution.
    from scripts.flow_sales_gap import normalize_admin_code
except ModuleNotFoundError:
    from flow_sales_gap import normalize_admin_code


PURPOSES = ["식사", "카페", "공부", "쇼핑", "여가문화"]

# The Seoul commercial-analysis service categories are mutually exclusive here.
# Keeping this map in code makes every later score inspectable and editable.
PURPOSE_INDUSTRIES = {
    "식사": {
        "한식음식점", "중식음식점", "일식음식점", "양식음식점", "제과점",
        "분식전문점", "치킨전문점", "패스트푸드점", "호프-간이주점", "일반주점",
    },
    "카페": {"커피-음료"},
    "공부": {
        "서적", "문구", "독서실", "일반교습학원", "외국어학원", "컴퓨터학원",
        "예술학원", "스포츠강습", "비디오/서적임대",
    },
    "쇼핑": {
        "일반의류", "한복점", "유아의류", "가방", "신발", "화장품", "귀금속",
        "시계및귀금속", "슈퍼마켓", "편의점", "전자상거래업", "가전제품", "가구",
        "안경", "완구", "화초", "애완동물", "운동/경기용품", "청과상", "미곡판매",
        "수산물판매", "육류판매", "반찬가게", "의약품", "중고차판매", "자동차부품",
        "조명용품", "섬유제품", "인테리어", "철물점", "핸드폰", "예술품", "악기",
    },
    "여가문화": {
        "노래방", "PC방", "당구장", "골프연습장", "볼링장", "기타오락장", "전자게임장",
        "녹음실", "DVD방", "무도장", "스포츠클럽", "레저용품", "여관", "호텔",
    },
}

FACILITY_COLUMNS = {
    "식사": [],
    "카페": [],
    "공부": ["대학교_수", "고등학교_수", "중학교_수", "초등학교_수"],
    "쇼핑": ["백화점_수", "슈퍼마켓_수"],
    "여가문화": ["극장_수", "숙박_시설_수"],
}

TIME_COLUMNS = {
    "식사": ["시간대_11~14_매출_금액", "시간대_17~21_매출_금액"],
    "카페": ["시간대_11~14_매출_금액", "시간대_14~17_매출_금액"],
    "공부": ["시간대_11~14_매출_금액", "시간대_14~17_매출_금액"],
    "쇼핑": ["시간대_14~17_매출_금액", "시간대_17~21_매출_금액"],
    "여가문화": ["시간대_17~21_매출_금액", "시간대_21~24_매출_금액"],
}


def map_industry_to_purpose(industry: str) -> str | None:
    """Return one of the five user-facing purposes, or None for excluded services."""
    name = str(industry).strip()
    for purpose, industries in PURPOSE_INDUSTRIES.items():
        if name in industries:
            return purpose
    return None


def purpose_time_columns(purpose: str) -> list[str]:
    return TIME_COLUMNS[purpose]


def _base_service_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["admin_code"] = out["행정동_코드"].map(normalize_admin_code)
    out["quarter"] = out["기준_년분기_코드"].astype(int)
    out["dong_name"] = out["행정동_코드_명"]
    out["purpose"] = out["서비스_업종_코드_명"].map(map_industry_to_purpose)
    return out[out["purpose"].notna()].copy()


def summarize_purpose_inputs(stores: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    """Aggregate official industry rows to quarter-dong-purpose features."""
    stores = _base_service_frame(stores)
    sales = _base_service_frame(sales)
    keys = ["quarter", "admin_code", "dong_name", "purpose"]

    store_agg = stores.groupby(keys, as_index=False).agg(purpose_store_count=("점포_수", "sum"))
    sales["_time_fit_amount"] = 0.0
    for purpose, indices in sales.groupby("purpose").groups.items():
        cols = [c for c in purpose_time_columns(purpose) if c in sales.columns]
        if cols:
            sales.loc[indices, "_time_fit_amount"] = sales.loc[indices, cols].sum(axis=1)
    sales_agg = sales.groupby(keys, as_index=False).agg(
        purpose_sales_amount=("당월_매출_금액", "sum"),
        purpose_time_fit_amount=("_time_fit_amount", "sum"),
    )
    out = store_agg.merge(sales_agg, on=keys, how="outer").fillna({"purpose_store_count": 0, "purpose_sales_amount": 0, "purpose_time_fit_amount": 0})
    total_stores = out.groupby(["quarter", "admin_code"])["purpose_store_count"].transform("sum")
    total_sales = out.groupby(["quarter", "admin_code"])["purpose_sales_amount"].transform("sum")
    out["purpose_store_share"] = np.divide(out["purpose_store_count"], total_stores, out=np.zeros(len(out)), where=total_stores > 0)
    out["purpose_sales_share"] = np.divide(out["purpose_sales_amount"], total_sales, out=np.zeros(len(out)), where=total_sales > 0)
    out["purpose_time_fit_share"] = np.divide(
        out["purpose_time_fit_amount"], out["purpose_sales_amount"], out=np.zeros(len(out)), where=out["purpose_sales_amount"] > 0
    )
    return out.sort_values(["quarter", "admin_code", "purpose"]).reset_index(drop=True)


def _percentile_score(values: pd.Series) -> pd.Series:
    values = values.fillna(0.0)
    if values.nunique(dropna=False) <= 1:
        return pd.Series(50.0, index=values.index)
    return values.rank(method="average", pct=True) * 100


def add_purpose_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Scale features within each quarter/purpose and add leakage-safe lag signal."""
    out = frame.copy()
    group_keys = ["quarter", "purpose"]
    out["store_count_percentile"] = out.groupby(group_keys)["purpose_store_count"].transform(lambda x: _percentile_score(np.log1p(x)))
    out["store_share_percentile"] = out.groupby(group_keys)["purpose_store_share"].transform(_percentile_score)
    out["time_fit_percentile"] = out.groupby(group_keys)["purpose_time_fit_share"].transform(_percentile_score)
    out["facility_percentile"] = out.groupby(group_keys)["facility_count"].transform(lambda x: _percentile_score(np.log1p(x)))
    out["sales_amount_percentile"] = out.groupby(group_keys)["purpose_sales_amount"].transform(lambda x: _percentile_score(np.log1p(x)))
    out["sales_share_percentile"] = out.groupby(group_keys)["purpose_sales_share"].transform(_percentile_score)
    out["purpose_supply_score"] = (
        0.55 * out["store_count_percentile"] + 0.30 * out["store_share_percentile"] + 0.15 * out["facility_percentile"]
    )
    out["current_sales_signal"] = (
        0.50 * out["sales_amount_percentile"] + 0.25 * out["sales_share_percentile"] + 0.25 * out["time_fit_percentile"]
    )
    out = out.sort_values(["purpose", "admin_code", "quarter"]).reset_index(drop=True)
    out["lagged_sales_signal"] = out.groupby(["purpose", "admin_code"])["current_sales_signal"].shift(1)
    out["purpose_model_input_score"] = 0.70 * out["purpose_supply_score"] + 0.30 * out["lagged_sales_signal"]
    return out.sort_values(["quarter", "admin_code", "purpose"]).reset_index(drop=True)


def add_facilities(frame: pd.DataFrame, facilities: pd.DataFrame) -> pd.DataFrame:
    facility = facilities.copy()
    facility["admin_code"] = facility["행정동_코드"].map(normalize_admin_code)
    facility["quarter"] = facility["기준_년분기_코드"].astype(int)
    keep = ["quarter", "admin_code"] + [c for cols in FACILITY_COLUMNS.values() for c in cols]
    keep = list(dict.fromkeys(c for c in keep if c in facility.columns))
    facility = facility[keep].groupby(["quarter", "admin_code"], as_index=False).sum(numeric_only=True)
    out = frame.merge(facility, on=["quarter", "admin_code"], how="left")
    for col in facility.columns:
        if col not in {"quarter", "admin_code"}:
            out[col] = out[col].fillna(0)
    out["facility_count"] = 0.0
    for purpose, cols in FACILITY_COLUMNS.items():
        available = [c for c in cols if c in out.columns]
        if available:
            mask = out["purpose"] == purpose
            out.loc[mask, "facility_count"] = out.loc[mask, available].sum(axis=1)
    return out


def _read_many(paths: list[Path]) -> pd.DataFrame:
    return pd.concat([pd.read_csv(path, encoding="cp949", low_memory=False) for path in paths], ignore_index=True)


def run(args: argparse.Namespace) -> None:
    root = Path(args.root)
    raw = root / "data/raw"
    stores = _read_many(sorted(raw.glob("seoul_commercial_stores_dong_20*.csv")))
    sales = _read_many(sorted(raw.glob("seoul_commercial_sales_dong_20*.csv")))
    facilities = pd.read_csv(raw / "seoul_attracting_facilities_dong.csv", encoding="cp949", low_memory=False)
    candidates = pd.read_csv(root / args.candidates, dtype={"emdcd": str})
    candidates = candidates[candidates["time_stability"] == "all_three_periods"].copy()
    candidates["admin_code"] = candidates["emdcd"].map(normalize_admin_code)

    frame = summarize_purpose_inputs(stores, sales)
    frame = frame.merge(candidates[["admin_code", "sggnm", "minimum_period_ratio", "mean_period_ratio"]], on="admin_code", how="inner")
    # A dong with no observed service in one purpose must remain a zero-feature
    # row; otherwise absence could be mistaken for unavailable data downstream.
    mapped_codes = frame["admin_code"].unique()
    mapped_candidates = candidates[candidates["admin_code"].isin(mapped_codes)].copy()
    dong_names = frame.groupby("admin_code")["dong_name"].first().to_dict()
    quarters = sorted(frame["quarter"].unique())
    grid = pd.MultiIndex.from_product(
        [quarters, mapped_candidates["admin_code"].unique(), PURPOSES], names=["quarter", "admin_code", "purpose"]
    ).to_frame(index=False)
    grid["dong_name"] = grid["admin_code"].map(dong_names)
    grid = grid.merge(mapped_candidates[["admin_code", "sggnm", "minimum_period_ratio", "mean_period_ratio"]], on="admin_code", how="left")
    measure_cols = ["purpose_store_count", "purpose_sales_amount", "purpose_time_fit_amount", "purpose_store_share", "purpose_sales_share", "purpose_time_fit_share"]
    frame = grid.merge(frame[["quarter", "admin_code", "purpose"] + measure_cols], on=["quarter", "admin_code", "purpose"], how="left")
    frame[measure_cols] = frame[measure_cols].fillna(0.0)
    frame = add_facilities(frame, facilities)
    frame = add_purpose_scores(frame)

    out = root / args.output
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "purpose_dong_quarter_features.csv", index=False, encoding="utf-8-sig")
    latest_quarter = int(frame["quarter"].max())
    latest = frame[frame["quarter"] == latest_quarter].copy()
    latest.to_csv(out / "purpose_dong_latest_features.csv", index=False, encoding="utf-8-sig")
    ranked = latest.sort_values(["purpose", "purpose_model_input_score"], ascending=[True, False])
    ranked.groupby("purpose", group_keys=False).head(15).to_csv(out / "purpose_feature_top15_latest.csv", index=False, encoding="utf-8-sig")

    lines = [
        "# 목적별 후보지 특징 변수", "",
        "## 용도", "",
        "이 표는 최종 추천 결과가 아니라, 30분 내 안정 도달 후보지의 목적별 특징을 수치화한 피처 마트다. 식사·카페·공부·쇼핑·여가문화에 대해 점포 구성, 집객시설, 매출의 시간대 패턴을 분리해 저장한다.", "",
        "## 점수 해석", "",
        "- `purpose_supply_score`: 같은 분기·같은 목적 안에서 점포 수(55%), 해당 목적의 점포 비중(30%), 관련 집객시설 수(15%)를 백분위로 합친 공급 신호다.",
        "- `current_sales_signal`: 같은 분기 매출 규모(50%), 목적별 매출 비중(25%), 해당 목적에 맞는 시간대 매출 비중(25%)을 합친 설명용 관측치다. 이 값은 동시점 결과이므로 추천 성능 검증의 입력으로 바로 쓰지 않는다.",
        "- `lagged_sales_signal`: 직전 분기의 `current_sales_signal`이다. `purpose_model_input_score`는 공급 신호 70%와 이 지연 신호 30%로 계산하여, 같은 분기 매출을 미리 안다고 가정하는 누수를 피한다.", "",
        "## 시설 매핑", "",
        "공부=대학교·초중고, 쇼핑=백화점·슈퍼마켓, 여가문화=극장·숙박시설을 보조 지표로 썼다. 식사와 카페는 행정동 단위 집객시설이 적절한 대표값이 아니어서 점포 구성과 시간대 소비를 중심으로 둔다.", "",
        "## 범위와 다음 단계", "",
        f"2023년 1분기부터 {latest_quarter // 10}년 {latest_quarter % 10}분기까지, 접근성 세 시간대 모두에서 절반 이상 출발지로부터 30분 내 도달한 행정동만 포함했다. 다음 단계에서는 이 특징과 B078의 실제 목적 이동량(전체 원본 접근 후)을 결합해 목적별 순위모형을 학습한다.",
    ]
    (out / "PURPOSE_FEATURES_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(frame):,} quarter-dong-purpose rows for {frame['admin_code'].nunique()} dongs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--candidates", default="data/processed/local_transit_30min/time_period_candidates.csv")
    parser.add_argument("--output", default="data/processed/purpose_features")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
