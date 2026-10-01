import pandas as pd

from scripts.flow_sales_gap import aggregate_inputs, classify_persistent_gap, normalize_admin_code, purpose_group


def test_normalize_admin_code_accepts_eight_and_ten_digits():
    assert normalize_admin_code(11230533) == "11230533"
    assert normalize_admin_code(1123053300) == "11230533"


def test_aggregate_inputs_sums_industries_without_double_counting():
    sales = pd.DataFrame({
        "기준_년분기_코드": [20251, 20251],
        "행정동_코드": [11230533, 11230533],
        "행정동_코드_명": ["용두동", "용두동"],
        "당월_매출_금액": [100, 200],
        "당월_매출_건수": [10, 20],
    })
    stores = pd.DataFrame({
        "기준_년분기_코드": [20251, 20251],
        "행정동_코드": [11230533, 11230533],
        "행정동_코드_명": ["용두동", "용두동"],
        "점포_수": [3, 4],
        "유사_업종_점포_수": [3, 5],
    })
    flow = pd.DataFrame({
        "기준_년분기_코드": [20251],
        "행정동_코드": [11230533],
        "행정동_코드_명": ["용두동"],
        "총_유동인구_수": [1000],
    })
    out = aggregate_inputs(sales, stores, flow)
    row = out.iloc[0]
    assert row["sales_amount"] == 300
    assert row["store_count"] == 7
    assert row["similar_store_count"] == 8
    assert row["floating_population"] == 1000


def test_classify_persistent_gap_requires_three_same_direction_quarters():
    frame = pd.DataFrame({
        "admin_code": ["1"] * 4 + ["2"] * 4,
        "quarter": [20251, 20252, 20253, 20254] * 2,
        "gap_z": [1.2, 1.3, 1.1, -0.2, -1.3, -1.2, 0.1, -1.4],
    })
    out = classify_persistent_gap(frame, threshold=1.0, min_quarters=3)
    labels = dict(zip(out["admin_code"], out["gap_type"]))
    assert labels["1"] == "목적소비형"
    assert labels["2"] == "통과형"


def test_purpose_group_maps_core_service_names():
    assert purpose_group("한식음식점") == "식사"
    assert purpose_group("커피-음료") == "카페"
    assert purpose_group("서적") == "공부"
    assert purpose_group("일반의류") == "쇼핑"
    assert purpose_group("노래방") == "여가문화"
