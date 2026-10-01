from __future__ import annotations

import json
import math
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / "tmp" / "eda_deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd
from pyproj import Transformer
import certifi

plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False


B078 = ROOT / "data" / "external" / "B078_PURPOSE_250M_202403_sample.csv"
B079 = ROOT / "data" / "external" / "B079_personal_card_inflow_dong_sample.csv"
BOUNDARY = ROOT / "data" / "external" / "seoul_municipalities_2015.geojson"
BOUNDARY_URL = "https://raw.githubusercontent.com/southkorea/seoul-maps/master/juso/2015/json/seoul_municipalities_geo_simple.json"
OUT = ROOT / "reports" / "eda" / "dongdaemun_50min_pilot"
FIG = OUT / "figures"
TAB = OUT / "tables"


def ensure_dirs() -> None:
    for p in (OUT, FIG, TAB):
        p.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"cannot decode {path}")


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    def in_polygon(poly: list) -> bool:
        if not poly or not MplPath(np.asarray(poly[0], dtype=float)).contains_point((lon, lat)):
            return False
        return not any(MplPath(np.asarray(hole, dtype=float)).contains_point((lon, lat)) for hole in poly[1:])

    if geometry["type"] == "Polygon":
        return in_polygon(geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return any(in_polygon(poly) for poly in geometry["coordinates"])
    return False


def district_lookup(lon: float, lat: float, features: list[dict]) -> str | None:
    for feature in features:
        if point_in_geometry(lon, lat, feature["geometry"]):
            return feature["properties"]["SIG_KOR_NM"]
    return None


def profile_table(df: pd.DataFrame, name: str) -> pd.DataFrame:
    rows = []
    for c in df.columns:
        rows.append(
            {
                "dataset": name,
                "column": c,
                "dtype": str(df[c].dtype),
                "non_null": int(df[c].notna().sum()),
                "missing_pct": round(float(df[c].isna().mean() * 100), 2),
                "n_unique": int(df[c].nunique(dropna=True)),
                "sample": " | ".join(map(str, df[c].dropna().astype(str).head(3).tolist())),
            }
        )
    return pd.DataFrame(rows)


def save_bar(series: pd.Series, title: str, ylabel: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    series.plot(kind="bar", ax=ax, color="#245a87")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    if not BOUNDARY.exists():
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(BOUNDARY_URL, context=context) as response:
            BOUNDARY.write_bytes(response.read())
    b078 = read_csv(B078)
    b079 = read_csv(B079)
    b078_source_columns = b078.columns.tolist()
    b079_source_columns = b079.columns.tolist()

    # B078: the demographic count columns jointly represent estimated movement volume.
    count_cols = [c for c in b078.columns if c.endswith("_CNT")]
    b078["MOVE_CNT_TOTAL"] = b078[count_cols].sum(axis=1, min_count=1)
    # The official B078 codebook defines MOVE_TIME as minutes, not seconds.
    b078["MOVE_TIME_MIN"] = b078["MOVE_TIME"]
    b078["MOVE_DIST_KM"] = b078["MOVE_DIST"] / 1000.0
    b078["SPEED_KMH"] = np.where(
        b078["MOVE_TIME"] > 0,
        b078["MOVE_DIST_KM"] / (b078["MOVE_TIME_MIN"] / 60.0),
        np.nan,
    )

    with BOUNDARY.open(encoding="utf-8") as f:
        features = json.load(f)["features"]
    transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    o_lon, o_lat = transformer.transform(b078["O_CELL_X"].to_numpy(), b078["O_CELL_Y"].to_numpy())
    d_lon, d_lat = transformer.transform(b078["D_CELL_X"].to_numpy(), b078["D_CELL_Y"].to_numpy())
    b078["O_LON"], b078["O_LAT"] = o_lon, o_lat
    b078["D_LON"], b078["D_LAT"] = d_lon, d_lat
    b078["O_DISTRICT"] = [district_lookup(x, y, features) for x, y in zip(o_lon, o_lat)]
    b078["D_DISTRICT"] = [district_lookup(x, y, features) for x, y in zip(d_lon, d_lat)]

    dong = b078[b078["O_DISTRICT"] == "동대문구"].copy()
    dong50 = dong[dong["MOVE_TIME_MIN"] <= 50].copy()

    purpose = (
        b078.groupby("MOVE_PURPOSE", dropna=False)
        .agg(rows=("MOVE_PURPOSE", "size"), movement=("MOVE_CNT_TOTAL", "sum"), median_minutes=("MOVE_TIME_MIN", "median"))
        .reset_index()
        .sort_values("movement", ascending=False)
    )
    purpose["movement_share_pct"] = purpose["movement"] / purpose["movement"].sum() * 100
    purpose.to_csv(TAB / "b078_purpose_summary.csv", index=False, encoding="utf-8-sig")

    time_bands = pd.cut(
        b078["MOVE_TIME_MIN"],
        bins=[0, 10, 20, 30, 40, 50, np.inf],
        labels=["0-10", "10-20", "20-30", "30-40", "40-50", "50+"],
        right=True,
        include_lowest=True,
    )
    tb = (
        b078.assign(time_band=time_bands)
        .groupby("time_band", observed=False)
        .agg(rows=("time_band", "size"), movement=("MOVE_CNT_TOTAL", "sum"), unique_destinations=("D_CELL_ID", "nunique"))
        .reset_index()
    )
    tb["movement_share_pct"] = tb["movement"] / tb["movement"].sum() * 100
    tb.to_csv(TAB / "b078_time_band_summary.csv", index=False, encoding="utf-8-sig")

    district_od = (
        b078.dropna(subset=["O_DISTRICT", "D_DISTRICT"])
        .groupby(["O_DISTRICT", "D_DISTRICT"], as_index=False)
        .agg(rows=("ETL_YMD", "size"), movement=("MOVE_CNT_TOTAL", "sum"), median_minutes=("MOVE_TIME_MIN", "median"))
        .sort_values("movement", ascending=False)
    )
    district_od.to_csv(TAB / "b078_sample_district_od.csv", index=False, encoding="utf-8-sig")
    dong50.to_csv(TAB / "b078_dongdaemun_origin_within_50min.csv", index=False, encoding="utf-8-sig")

    card_by_industry = (
        b079.groupby("업종대분류", dropna=False)
        .agg(rows=("업종대분류", "size"), amount=("카드이용금액계", "sum"), transactions=("카드이용건수계", "sum"))
        .reset_index()
        .sort_values("amount", ascending=False)
    )
    card_by_industry["avg_ticket"] = card_by_industry["amount"] / card_by_industry["transactions"].replace(0, np.nan)
    card_by_industry.to_csv(TAB / "b079_industry_summary.csv", index=False, encoding="utf-8-sig")

    customer = (
        b079.groupby(["고객주소광역시도", "고객주소시군구"], dropna=False)
        .agg(rows=("기준일자", "size"), amount=("카드이용금액계", "sum"), transactions=("카드이용건수계", "sum"))
        .reset_index()
        .sort_values("amount", ascending=False)
    )
    customer.to_csv(TAB / "b079_customer_origin_summary.csv", index=False, encoding="utf-8-sig")

    dong_card = b079[(b079["고객주소광역시도"] == "서울") & (b079["고객주소시군구"] == "동대문구")].copy()
    dong_card.to_csv(TAB / "b079_dongdaemun_customer_rows.csv", index=False, encoding="utf-8-sig")

    profiles = pd.concat([profile_table(b078.drop(columns=["O_LON", "O_LAT", "D_LON", "D_LAT"]), "B078"), profile_table(b079, "B079")])
    profiles.to_csv(TAB / "schema_profile.csv", index=False, encoding="utf-8-sig")

    quality = pd.DataFrame(
        [
            {"dataset": "B078", "rows": len(b078), "columns": len(b078_source_columns), "duplicate_rows": int(b078[b078_source_columns].duplicated().sum()), "missing_cells": int(b078[b078_source_columns].isna().sum().sum())},
            {"dataset": "B079", "rows": len(b079), "columns": len(b079_source_columns), "duplicate_rows": int(b079[b079_source_columns].duplicated().sum()), "missing_cells": int(b079[b079_source_columns].isna().sum().sum())},
        ]
    )
    quality.to_csv(TAB / "data_quality_summary.csv", index=False, encoding="utf-8-sig")

    save_bar(purpose.set_index("MOVE_PURPOSE")["movement"], "B078 sample: movement by purpose code", "estimated movement", FIG / "b078_purpose_movement.png")
    save_bar(tb.set_index("time_band")["movement_share_pct"], "B078 sample: movement-time distribution", "movement share (%)", FIG / "b078_time_bands.png")
    save_bar(card_by_industry.head(12).set_index("업종대분류")["amount"], "B079 sample: card amount by industry", "card amount", FIG / "b079_industry_amount.png")

    # A small machine-readable facts file keeps the narrative reproducible.
    facts = {
        "b078_rows": int(len(b078)),
        "b078_source_columns": int(len(b078_source_columns)),
        "b078_date_min": str(b078["ETL_YMD"].min()),
        "b078_date_max": str(b078["ETL_YMD"].max()),
        "b078_move_time_minutes_min": int(b078["MOVE_TIME"].min()),
        "b078_move_time_minutes_median": float(b078["MOVE_TIME"].median()),
        "b078_move_time_minutes_max": int(b078["MOVE_TIME"].max()),
        "b078_move_distance_median_m": float(b078["MOVE_DIST"].median()),
        "b078_speed_kmh_median": float(b078["SPEED_KMH"].replace([np.inf, -np.inf], np.nan).median()),
        "b078_within_50min_rows_all_sample": int((b078["MOVE_TIME_MIN"] <= 50).sum()),
        "b078_within_50min_movement_share_all_sample_pct": float(b078.loc[b078["MOVE_TIME_MIN"] <= 50, "MOVE_CNT_TOTAL"].sum() / b078["MOVE_CNT_TOTAL"].sum() * 100),
        "b078_origin_mapped_to_seoul_rows": int(b078["O_DISTRICT"].notna().sum()),
        "b078_dongdaemun_origin_rows": int(len(dong)),
        "b078_dongdaemun_origin_within_50min_rows": int(len(dong50)),
        "b079_rows": int(len(b079)),
        "b079_source_columns": int(len(b079_source_columns)),
        "b079_date_min": str(b079["기준일자"].min()),
        "b079_date_max": str(b079["기준일자"].max()),
        "b079_missing_customer_district_rows": int(b079["고객주소시군구"].isna().sum()),
        "b079_dongdaemun_customer_rows": int(len(dong_card)),
        "b079_total_amount": int(b079["카드이용금액계"].sum()),
        "b079_total_transactions": int(b079["카드이용건수계"].sum()),
        "b079_avg_ticket": float(b079["카드이용금액계"].sum() / b079["카드이용건수계"].sum()),
        "direct_b078_b079_join_valid": False,
        "reason": "sample periods differ and B078 is grid OD while B079 is aggregated customer-region to merchant-dong consumption",
    }
    (OUT / "eda_facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")

    top_purposes = purpose.head(5).to_dict("records")
    top_industries = card_by_industry.head(5).to_dict("records")
    report = f"""# 동대문구 50분 상권 추천 파일럿 — B078·B079 샘플 EDA

기준일: 2026-08-22  
실행 스크립트: `scripts/eda_dongdaemun_pilot.py`

## 1. 결론 먼저

현재 작업공간의 실제 데이터는 B078 **{len(b078):,}행 샘플**과 B079 **{len(b079):,}행 샘플**뿐이다. B078은 2024년 3월, B079는 2023년 1월 1일 자료로 시점과 공간단위가 다르므로 두 파일을 직접 결합해 유동–카드매출 괴리를 계산할 수 없다. 특히 유동인구–매출 비선형 관계를 추정하려면 서울 상권분석서비스의 상권별 유동인구·추정매출·점포·영역 원본이 추가로 필요하다.

B078 좌표를 EPSG:5179에서 WGS84로 변환하고 서울 자치구 경계에 포인트 결합했다. 이 공개 샘플에서 서울 자치구로 매핑된 출발행은 **{facts['b078_origin_mapped_to_seoul_rows']:,}행**, 동대문구 출발행은 **{len(dong):,}행**, 그중 50분 이내는 **{len(dong50):,}행**이다. 표본이 극히 작거나 0이면 동대문구 50분 후보 상권 수와 목적 분포를 추정하지 않는다. 원본이 들어오면 동일 코드로 즉시 재실행할 수 있다.

## 2. B078 이동 샘플

- 기간: {facts['b078_date_min']}–{facts['b078_date_max']}
- 원본 행/열: {len(b078):,}행 × {len(b078_source_columns):,}열
- 이동시간: 최소 {facts['b078_move_time_minutes_min']:,}분, 중앙값 {facts['b078_move_time_minutes_median']:.0f}분, 최대 {facts['b078_move_time_minutes_max']:,}분이다. 공식 B078 설명서가 `MOVE_TIME`을 분 단위로 정의하므로 별도의 `/60` 환산을 하지 않았다. 장시간 값은 월간 표본 원자료에서 재확인해야 한다.
- 전체 샘플에서 50분 이내 행 비중은 {(b078['MOVE_TIME_MIN'] <= 50).mean()*100:.1f}%, 이동량 비중은 {facts['b078_within_50min_movement_share_all_sample_pct']:.1f}%다. 이는 동대문구 결과가 아니라 랜덤 샘플 전체 결과다.
- 이동량은 성·연령별 `*_CNT` 열을 합한 `MOVE_CNT_TOTAL`로 계산했다. 행 수 자체를 사람 수로 해석하지 않는다.
- 목적코드는 숫자만 존재하므로 코드북 없이 ‘식사·쇼핑·문화’로 임의 번역하지 않는다.

상위 목적코드(추정 이동량 기준):
"""
    for r in top_purposes:
        report += f"\n- 코드 {r['MOVE_PURPOSE']}: 이동량 {r['movement']:.2f}, 비중 {r['movement_share_pct']:.1f}%, 중앙 이동시간 {r['median_minutes']:.1f}분"

    report += f"""

## 3. B079 카드소비 샘플

- 기간: {facts['b079_date_min']} 하루
- 원본 행/열: {len(b079):,}행 × {len(b079_source_columns):,}열
- 총 이용금액 {facts['b079_total_amount']:,}원, 총 이용건수 {facts['b079_total_transactions']:,}건, 단순 평균 객단가 {facts['b079_avg_ticket']:,.0f}원
- 고객주소 시군구 결측은 {facts['b079_missing_customer_district_rows']:,}행이다.
- 고객주소가 서울 동대문구인 행은 {len(dong_card):,}행이다. 이는 실제 출발시점이 아니라 거주지 프록시다.
- 가맹점 행정동은 있으나 상권코드는 없으므로 상권영역과 공간/코드 매핑이 필요하다.

상위 업종(이용금액 기준):
"""
    for r in top_industries:
        report += f"\n- {r['업종대분류']}: {int(r['amount']):,}원, {int(r['transactions']):,}건, 객단가 {r['avg_ticket']:,.0f}원"

    report += """

## 4. 유동–매출 괴리 분석의 올바른 정의

‘선형관계인 지역을 제거’하기보다, 먼저 상권별 기대매출을 추정하고 잔차가 큰 지역을 찾는다. 1차 기준선은 `log1p(매출) ~ spline(log1p(유동)) + log1p(점포수) + 면적 + 상권유형 + 업종구성`이다. 선형회귀와 GAM의 교차검증 성능을 비교하고, LightGBM/CatBoost는 비선형 기준선으로 둔다. 공통적으로 큰 양의 잔차는 고전환, 큰 음의 잔차는 저전환 후보이며 원인으로 목적 유입, 환승·통과, 체류시간, 객단가, 업종구성, 학교·업무·시장·도매 기능, 경계오차를 점검한다.

B078 목적분포는 괴리 원인 설명변수다. 예를 들어 특정 상권의 고전환이 쇼핑·식사 목적 유입과 함께 나타나는지, 저전환이 통근·통학·귀가 목적과 함께 나타나는지를 집단 수준에서 검증한다. B079는 개인을 연결하지 않고 동대문구 거주자 집단의 소비지역·업종 분포로 외부 검증한다.

## 5. 한 학기 로드맵

1. 1–3주: 원본·코드북 확보, 기간 통일, 좌표·행정동·상권 매핑, 10/20/30/40/50분 접근권역 생성
2. 4–6주: 상권별 유동–매출 선형·GAM·부스팅 기준선 비교, 안정적 잔차 후보 선정
3. 7–9주: B078 목적·시간·연령 구조와 B079 소비지역·업종을 이용한 괴리 원인 분석
4. 10–12주: 목적별 후보생성 + 설명가능 점수 + Hidden Destination 재정렬로 1차 추천 서비스 구축
5. 13–15주: 점포명·카테고리·메뉴·소개글·리뷰 텍스트에 KoRoBERTa/Sentence-BERT 임베딩을 적용해 점포 재정렬, 오프라인 평가와 사용자 테스트

RoBERTa 계열은 유동·매출을 예측하는 주력모델이 아니라 점포 텍스트 적합도 계산에 사용한다. 수치형 상권 추천은 회귀·랭킹·선택모형이 담당하고, 텍스트 모델은 이미 생성된 상권 후보 안에서 점포 순서를 조정한다.

## 6. 원본 확보 후 필수 산출물

- `dongdaemun_10_20_30_40_50min_coverage.csv`: 시간권역별 후보 상권·목적·이동량 포괄률
- `flow_sales_model_comparison.csv`: 선형·GAM·LightGBM/CatBoost의 시계열 교차검증 성능
- `flow_sales_gap_candidates.csv`: 기대매출, 실제매출, 잔차, 달성률, 안정성
- `gap_reason_features.csv`: B078 목적·시간·연령, B079 업종·소비, 점포·토지이용 특징
- `recommendation_candidates.csv`: 접근성·목 적합도·괴리·텍스트 점수와 추천 사유

## 7. 해석 제한

- 현재 샘플만으로 동대문구 50분 추천 성능이나 유동–매출 관계를 결론 내릴 수 없다.
- B078과 B079는 개인키가 없으며 서로 다른 집단·공간단위이므로 “이 사람이 이 목적으로 와서 결제했다”고 말할 수 없다.
- 잔차는 인과효과나 숨은 명소 확정값이 아니라 추가 조사 후보를 찾는 탐색적 신호다.
- 사용한 서울 자치구 경계는 공간 필터 구현 검증용 2015 단순화 경계이며, 최종 분석에서는 최신 공식 경계를 사용한다.
"""
    (OUT / "EDA_REPORT.md").write_text(report, encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
