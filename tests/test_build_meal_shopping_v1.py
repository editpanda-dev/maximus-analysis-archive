import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon


def test_taxonomy_moves_bakery_and_pubs_out_of_meal_and_excludes_non_destination_retail():
    from scripts.build_meal_shopping_v1 import map_meal_subcategory, map_shopping_subcategory

    assert map_meal_subcategory("한식음식점") == "한식"
    assert map_meal_subcategory("분식전문점") == "간편식"
    assert map_meal_subcategory("제과점") is None
    assert map_meal_subcategory("호프-간이주점") is None
    assert map_shopping_subcategory("일반의류") == "패션·뷰티"
    assert map_shopping_subcategory("슈퍼마켓") == "식품·생활"
    assert map_shopping_subcategory("전자상거래업") is None
    assert map_shopping_subcategory("주류도매") is None


def test_meal_price_band_is_relative_to_same_menu_and_keeps_missing_ticket_unknown():
    from scripts.build_meal_shopping_v1 import add_meal_price_bands

    frame = pd.DataFrame({
        "industry": ["한식음식점"] * 4 + ["분식전문점"],
        "lunch_sales_amount": [100, 200, 300, 400, 100],
        "lunch_sales_count": [10, 10, 10, 10, 0],
    })
    result = add_meal_price_bands(frame)

    assert result.loc[0, "meal_price_band"] == "저가"
    assert result.loc[3, "meal_price_band"] == "고가"
    assert result.loc[4, "meal_price_band"] == "정보없음"


def test_market_exclusion_is_conservative_and_auditable():
    from scripts.build_meal_shopping_v1 import classify_market_channel

    assert classify_market_channel("청량종합도매시장", "전통시장") == "도매·전문시장"
    assert classify_market_channel("답십리 건축자재시장", "전통시장") == "도매·전문시장"
    assert classify_market_channel("회기시장", "전통시장") == "일반소매"
    assert classify_market_channel("건대입구역", "발달상권") == "일반상권"


def _areas():
    return gpd.GeoDataFrame(
        {
            "area_code": ["1", "2", "3"],
            "area_name": ["일반", "관광", "청량종합도매시장"],
            "area_type_name": ["골목상권", "관광특구", "전통시장"],
        },
        geometry=[
            Polygon([(127, 37.5), (127.001, 37.5), (127.001, 37.501), (127, 37.501)]),
            Polygon([(127.01, 37.5), (127.012, 37.5), (127.012, 37.502), (127.01, 37.502)]),
            Polygon([(127.02, 37.5), (127.021, 37.5), (127.021, 37.501), (127.02, 37.501)]),
        ],
        crs="EPSG:4326",
    )


def test_feature_mart_keeps_every_area_and_only_imputes_missing_shopping_total():
    from scripts.build_meal_shopping_v1 import build_meal_shopping_v1

    candidates = pd.DataFrame({
        "area_code": ["1", "2", "3"],
        "area_name": ["일반", "관광", "청량종합도매시장"],
        "area_type_name": ["골목상권", "관광특구", "전통시장"],
        "minimum_period_ratio": [0.8, 0.9, 0.7],
        "store_count_total": [20, 100, 30],
    })
    stores = pd.DataFrame({
        "stdr_yyqu_cd": [20254] * 5,
        "trdar_cd": [1, 1, 2, 3, 3],
        "svc_induty_cd_nm": ["한식음식점", "일반의류", "한식음식점", "슈퍼마켓", "편의점"],
        "stor_co": [4, 2, 20, 3, 2],
    })
    sales = pd.DataFrame({
        "기준_년분기_코드": [20254, 20254, 20254],
        "상권_코드": [1, 1, 2],
        "서비스_업종_코드_명": ["한식음식점", "일반의류", "한식음식점"],
        "당월_매출_금액": [400, 200, 3000],
        "당월_매출_건수": [40, 10, 100],
        "시간대_11~14_매출_금액": [200, 0, 1000],
        "시간대_건수~14_매출_건수": [20, 0, 40],
        "시간대_14~17_매출_금액": [50, 100, 500],
        "시간대_17~21_매출_금액": [100, 50, 1000],
    })

    result, detail, audit = build_meal_shopping_v1(stores, sales, candidates, _areas(), quarter=20254)

    assert len(result) == 6
    assert result.area_code.nunique() == 3
    missing_shop = result[(result.area_code == "0000003") & (result.purpose == "쇼핑")].iloc[0]
    assert missing_shop.sales_observed is False or not bool(missing_shop.sales_observed)
    assert missing_shop.sales_imputed
    assert missing_shop.sales_category_coverage == 0
    assert missing_shop.store_식품·생활 == 5
    assert "추정 매출" in missing_shop.recommendation_reason
    assert not missing_shop.recommendation_high_confidence
    tourism = result[(result.area_code == "0000002") & (result.purpose == "식사")].iloc[0]
    wholesale = result[(result.area_code == "0000003") & (result.purpose == "쇼핑")].iloc[0]
    normal_meal = result[(result.area_code == "0000001") & (result.purpose == "식사")].iloc[0]
    assert normal_meal.store_한식 == 4
    assert not tourism.recommendation_eligible
    assert not wholesale.recommendation_eligible
    assert set(detail.purpose) <= {"식사", "쇼핑"}
    assert audit["area_count"] == 3
    assert audit["shopping_high_confidence_area_count"] == 1


def test_combined_ranking_requires_both_purposes_to_be_eligible():
    from scripts.build_meal_shopping_v1 import build_combined_ranking

    frame = pd.DataFrame({
        "area_code": ["1", "1", "2", "2"],
        "area_name": ["가", "가", "나", "나"],
        "purpose": ["식사", "쇼핑", "식사", "쇼핑"],
        "size_adjusted_score": [90, 70, 100, 100],
        "recommendation_eligible": [True, True, True, False],
        "recommendation_high_confidence": [True, True, True, True],
    })

    combined = build_combined_ranking(frame)

    assert combined.area_code.tolist() == ["1"]
    assert combined.iloc[0].combined_score == 80
