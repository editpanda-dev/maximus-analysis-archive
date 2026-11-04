import pandas as pd


def test_build_2025_polygon_mapping_keeps_only_year_matched_rows_and_marks_direct_join():
    from scripts.build_2025_polygon_purpose_mapping import build_2025_polygon_mapping

    features = pd.DataFrame({
        "quarter": [20244, 20251, 20254],
        "area_code": [3120001, 3120001, 3120002],
        "area_name": ["가", "가", "나"],
        "area_type_name": ["골목상권", "골목상권", "발달상권"],
        "purpose": ["식사", "카페", "공부"],
        "purpose_store_count": [3, 4, 5],
        "purpose_sales_amount": [100, 200, 300],
        "purpose_time_fit_amount": [80, 150, 200],
        "purpose_supply_score": [40, 50, 60],
        "path_v0_score": [30, 40, 50],
    })

    result = build_2025_polygon_mapping(features)

    assert result["quarter"].tolist() == [20251, 20254]
    assert result["area_code"].tolist() == ["3120001", "3120002"]
    assert result["source_year"].eq(2025).all()
    assert result["mapping_method"].eq("상권코드 직접 결합").all()
    assert result["historical_2025_use_allowed"].eq(True).all()
