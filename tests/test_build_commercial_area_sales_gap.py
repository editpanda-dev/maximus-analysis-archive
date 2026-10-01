import pandas as pd

from scripts.build_commercial_area_sales_gap import build_gap_features


def test_build_gap_features_aggregates_official_areas_by_quarter():
    candidates = pd.DataFrame({
        "area_code": ["3110001", "3110002"],
        "area_name": ["가", "나"],
        "area_type_name": ["골목상권", "발달상권"],
        "area_m2": [1_000.0, 2_000.0],
    })
    stores = pd.DataFrame({
        "stdr_yyqu_cd": [20251, 20251, 20252, 20252],
        "trdar_cd": [3110001, 3110001, 3110002, 3110002],
        "svc_induty_cd_nm": ["한식음식점", "커피-음료", "한식음식점", "한식음식점"],
        "stor_co": [10, 5, 4, 6],
    })
    sales = pd.DataFrame({
        "기준_년분기_코드": [20251, 20251, 20252, 20252],
        "상권_코드": [3110001, 3110001, 3110002, 3110002],
        "서비스_업종_코드_명": ["한식음식점", "커피-음료", "한식음식점", "한식음식점"],
        "당월_매출_금액": [100, 50, 40, 60],
    })

    result = build_gap_features(stores, sales, candidates)

    assert len(result) == 4
    first = result[(result.quarter == 20251) & (result.area_code == "3110001")].iloc[0]
    assert first.store_count == 15
    assert first.sales_amount == 150
    assert first.industry_entropy > 0
    assert set(result.area_code) == {"3110001", "3110002"}
