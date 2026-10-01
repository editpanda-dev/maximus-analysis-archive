import pandas as pd

from scripts.build_purpose_features import (
    add_purpose_scores,
    map_industry_to_purpose,
    purpose_time_columns,
    summarize_purpose_inputs,
)


def test_industry_mapping_covers_recommendation_purposes():
    assert map_industry_to_purpose("한식음식점") == "식사"
    assert map_industry_to_purpose("커피-음료") == "카페"
    assert map_industry_to_purpose("독서실") == "공부"
    assert map_industry_to_purpose("일반의류") == "쇼핑"
    assert map_industry_to_purpose("노래방") == "여가문화"
    assert map_industry_to_purpose("자동차수리") is None


def test_time_columns_are_explicit_by_purpose():
    assert purpose_time_columns("식사") == ["시간대_11~14_매출_금액", "시간대_17~21_매출_금액"]
    assert "시간대_21~24_매출_금액" in purpose_time_columns("여가문화")


def test_summarize_inputs_aggregates_each_purpose_without_service_double_counting():
    stores = pd.DataFrame({
        "기준_년분기_코드": [20251, 20251, 20251],
        "행정동_코드": [11230533, 11230533, 11230533],
        "행정동_코드_명": ["용두동"] * 3,
        "서비스_업종_코드_명": ["한식음식점", "커피-음료", "자동차수리"],
        "점포_수": [10, 4, 8],
    })
    sales = pd.DataFrame({
        "기준_년분기_코드": [20251, 20251],
        "행정동_코드": [11230533, 11230533],
        "행정동_코드_명": ["용두동", "용두동"],
        "서비스_업종_코드_명": ["한식음식점", "커피-음료"],
        "당월_매출_금액": [1000, 200],
        "시간대_11~14_매출_금액": [500, 10],
        "시간대_14~17_매출_금액": [100, 100],
        "시간대_17~21_매출_금액": [300, 70],
        "시간대_21~24_매출_금액": [100, 20],
    })
    out = summarize_purpose_inputs(stores, sales)
    meal = out[(out["purpose"] == "식사")].iloc[0]
    cafe = out[(out["purpose"] == "카페")].iloc[0]
    assert meal["purpose_store_count"] == 10
    assert meal["purpose_sales_amount"] == 1000
    assert meal["purpose_time_fit_share"] == 0.8
    assert cafe["purpose_store_count"] == 4


def test_scores_are_bounded_and_lagged_within_each_dong():
    frame = pd.DataFrame({
        "quarter": [20251, 20252, 20251, 20252],
        "admin_code": ["1", "1", "2", "2"],
        "dong_name": ["가", "가", "나", "나"],
        "purpose": ["식사"] * 4,
        "purpose_store_count": [10, 11, 2, 3],
        "purpose_store_share": [.5, .5, .2, .2],
        "purpose_sales_amount": [100, 120, 20, 25],
        "purpose_sales_share": [.6, .6, .2, .2],
        "purpose_time_fit_share": [.8, .8, .4, .4],
        "facility_count": [0, 0, 0, 0],
    })
    out = add_purpose_scores(frame)
    assert out["purpose_supply_score"].between(0, 100).all()
    assert out.loc[(out.admin_code == "1") & (out.quarter == 20251), "lagged_sales_signal"].isna().all()
    assert out.loc[(out.admin_code == "1") & (out.quarter == 20252), "lagged_sales_signal"].notna().all()
