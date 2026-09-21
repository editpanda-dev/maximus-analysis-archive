import pandas as pd

from scripts.build_commercial_area_purpose_features import (
    build_features,
    combine_path_score,
    map_industry_to_recommendation_purpose,
)


def test_study_purpose_keeps_only_stay_for_study_industries():
    """The user-facing study purpose must represent studying on site, not supplies."""
    assert map_industry_to_recommendation_purpose("독서실") == "공부"
    assert map_industry_to_recommendation_purpose("문구") is None
    assert map_industry_to_recommendation_purpose("서적") is None
    assert map_industry_to_recommendation_purpose("일반교습학원") is None


def test_study_stay_score_does_not_impute_a_missing_sales_signal():
    frame = pd.DataFrame({
        "purpose": ["공부", "식사"],
        "purpose_supply_score": [80.0, 80.0],
        "lagged_sales_signal": [50.0, 50.0],
        "access_score": [90.0, 90.0],
    })

    result = combine_path_score(frame)

    assert result.iloc[0] == 81.0  # study stay: supply 90% + access 10%
    assert result.iloc[1] == 71.0  # other purposes: supply 70% + lagged sales 30%


def test_build_features_uses_official_area_codes_and_lagged_sales():
    candidates = pd.DataFrame({
        "area_code": ["3110001", "3110002"],
        "area_name": ["가", "나"],
        "area_type_name": ["골목상권", "발달상권"],
        "minimum_period_ratio": [0.9, 0.7],
        "mean_period_ratio": [0.95, 0.8],
    })
    stores = pd.DataFrame({
        "stdr_yyqu_cd": [20251, 20251, 20252, 20252],
        "trdar_cd": [3110001, 3110002, 3110001, 3110002],
        "svc_induty_cd_nm": ["한식음식점"] * 4,
        "stor_co": [10, 5, 12, 6],
    })
    sales = pd.DataFrame({
        "기준_년분기_코드": [20251, 20251, 20252, 20252],
        "상권_코드": [3110001, 3110002, 3110001, 3110002],
        "서비스_업종_코드_명": ["한식음식점"] * 4,
        "당월_매출_금액": [100, 50, 500, 60],
        "시간대_11~14_매출_금액": [60, 20, 300, 20],
        "시간대_17~21_매출_금액": [30, 20, 150, 30],
    })

    result = build_features(stores, sales, candidates)
    first = result[(result.area_code == "3110001") & (result.purpose == "식사")].sort_values("quarter")

    assert len(result) == 2 * 2 * 5
    assert pd.isna(first.iloc[0].lagged_sales_signal)
    assert first.iloc[1].lagged_sales_signal == first.iloc[0].current_sales_signal
    assert first.iloc[1].path_v0_score == (
        0.7 * first.iloc[1].purpose_supply_score + 0.3 * first.iloc[1].lagged_sales_signal
    )


def test_excluding_learning_goods_from_study_does_not_change_food_store_share():
    candidates = pd.DataFrame({"area_code": ["3110001"], "minimum_period_ratio": [0.8]})
    stores = pd.DataFrame({
        "stdr_yyqu_cd": [20251, 20251],
        "trdar_cd": [3110001, 3110001],
        "svc_induty_cd_nm": ["한식음식점", "문구"],
        "stor_co": [10, 100],
    })
    sales = pd.DataFrame({
        "기준_년분기_코드": [20251, 20251],
        "상권_코드": [3110001, 3110001],
        "서비스_업종_코드_명": ["한식음식점", "서적"],
        "당월_매출_금액": [100, 900],
        "시간대_11~14_매출_금액": [60, 100],
        "시간대_17~21_매출_금액": [30, 100],
    })

    result = build_features(stores, sales, candidates)
    food = result[(result.purpose == "식사")].iloc[0]

    assert food.purpose_store_share == 10 / 110
    assert food.purpose_sales_share == 100 / 1000
