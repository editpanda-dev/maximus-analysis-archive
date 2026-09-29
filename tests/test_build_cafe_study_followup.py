import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon


def test_build_review_queue_keeps_only_pois_linked_to_candidate_areas():
    from scripts.build_cafe_study_followup import build_review_queue

    areas = gpd.GeoDataFrame(
        {"area_code": ["A", "B"], "area_name": ["가", "나"]},
        geometry=[
            Polygon([(127.0, 37.0), (127.01, 37.0), (127.01, 37.01), (127.0, 37.01)]),
            Polygon([(127.1, 37.1), (127.11, 37.1), (127.11, 37.11), (127.1, 37.11)]),
        ],
        crs="EPSG:4326",
    )
    queue = pd.DataFrame(
        {
            "place_id": ["1", "2", "3"],
            "place_name": ["내부 카페", "가까운 카페", "먼 카페"],
            "source_dataset": ["kakao", "kakao", "kakao"],
        }
    )
    poi = pd.DataFrame(
        {
            "place_id": ["1", "2", "3"],
            "longitude": [127.005, 127.012, 127.5],
            "latitude": [37.005, 37.005, 37.5],
            "category_name": ["음식점 > 카페", "음식점 > 카페", "음식점 > 카페"],
        }
    )

    result = build_review_queue(queue, poi, areas, euclidean_radius_m=400)

    assert set(result["place_id"]) == {"1", "2"}
    assert result.loc[result["place_id"] == "1", "inside_official_area"].iat[0]
    assert result.loc[result["place_id"] == "1", "matched_area_codes"].iat[0] == "A"
    assert not result.loc[result["place_id"] == "2", "inside_official_area"].iat[0]
    assert result.loc[result["place_id"] == "2", "matched_area_codes"].iat[0] == "A"


def test_add_size_adjusted_scores_keeps_complete_and_supply_only_cohorts_separate():
    from scripts.build_cafe_study_followup import add_size_adjusted_scores

    frame = pd.DataFrame(
        {
            "area_code": ["1", "2", "3", "4"],
            "area_km2": [0.1, 0.2, 0.1, 0.3],
            "total_stores_2025q4": [100, 200, 100, 300],
            "coffee_stores": [10, 20, 5, 30],
            "bakery_stores": [5, 10, 2, 15],
            "coffee_supply_score": [50.0, 70.0, 30.0, 90.0],
            "bakery_supply_score": [50.0, 70.0, 30.0, 90.0],
            "coffee_full_score": [60.0, 80.0, None, 95.0],
            "bakery_full_score": [60.0, 80.0, None, 95.0],
            "score_status": ["complete", "complete", "supply_only", "complete"],
            "recommendation_eligible": [True, True, True, False],
        }
    )

    result = add_size_adjusted_scores(frame)

    assert result.loc[result["area_code"] == "3", "cafe_size_adjusted_full_score"].isna().all()
    assert result.loc[result["area_code"] == "3", "cafe_size_adjusted_supply_only_score"].notna().all()
    assert result.loc[result["area_code"] == "4", "cafe_size_adjusted_full_rank"].isna().all()
    assert result.loc[result["area_code"] == "1", "cafe_size_adjusted_full_rank"].notna().all()
    assert result["cafe_size_adjustment_method"].eq("ols_residual_log_store_count").all()
