import pandas as pd


def test_build_leisure_enrichment_keeps_only_leisure_and_ranks_poi_augmented_score():
    from scripts.build_leisure_poi_enrichment import build_leisure_enrichment

    rankings = pd.DataFrame({
        "quarter": [20254, 20254, 20254],
        "area_code": ["3000001", "3000002", "3000001"],
        "purpose": ["여가문화", "여가문화", "카페"],
        "area_name": ["가", "나", "가"],
        "path_v0_score": [80.0, 80.0, 99.0],
        "purpose_rank": [1, 2, 1],
    })
    poi = pd.DataFrame({
        "area_code": ["3000001", "3000002"],
        "purpose": ["여가문화", "여가문화"],
        "feature_snapshot_date": ["2026-09-16", "2026-09-16"],
        "is_static_auxiliary": [1, 1],
        "historical_2025_use_allowed": [0, 0],
        "coverage_status": ["source_snapshot_partial", "source_snapshot_partial"],
        "operation_status": ["mixed_source_status", "mixed_source_status"],
        "culture_inside_count": [4, 0],
        "culture_buffer400_count": [10, 1],
        "culture_core_buffer400_count": [10, 1],
        "culture_buffer400_diversity": [5, 1],
        "poi_cinema_buffer400_count": [2, 0],
        "poi_performance_hall_buffer400_count": [1, 0],
        "poi_exhibition_space_buffer400_count": [3, 0],
        "poi_park_buffer400_count": [2, 0],
        "poi_sports_facility_buffer400_count": [1, 0],
    })

    result = build_leisure_enrichment(rankings, poi)

    assert set(result["purpose"]) == {"여가문화"}
    assert len(result) == 2
    assert result.iloc[0]["area_code"] == "3000001"
    assert result.iloc[0]["leisure_poi_rank"] == 1
    assert result["leisure_poi_rank"].nunique() == len(result)
    assert result["historical_2025_use_allowed"].eq(False).all()
    assert result["poi_enriched_score"].between(0, 100).all()


def test_build_leisure_enrichment_breaks_score_ties_by_area_code():
    from scripts.build_leisure_poi_enrichment import build_leisure_enrichment

    rankings = pd.DataFrame({
        "quarter": [20254, 20254], "area_code": ["3000002", "3000001"],
        "purpose": ["여가문화", "여가문화"], "area_name": ["나", "가"],
        "path_v0_score": [80.0, 80.0], "purpose_rank": [1, 2],
    })
    poi = pd.DataFrame({
        "area_code": ["3000002", "3000001"], "purpose": ["여가문화", "여가문화"],
        "feature_snapshot_date": ["2026-09-16", "2026-09-16"], "is_static_auxiliary": [1, 1],
        "historical_2025_use_allowed": [0, 0], "coverage_status": ["partial", "partial"],
        "operation_status": ["mixed", "mixed"], "culture_inside_count": [1, 1],
        "culture_buffer400_count": [1, 1], "culture_core_buffer400_count": [1, 1],
        "culture_buffer400_diversity": [1, 1], "poi_cinema_buffer400_count": [0, 0],
        "poi_performance_hall_buffer400_count": [0, 0], "poi_exhibition_space_buffer400_count": [0, 0],
        "poi_park_buffer400_count": [0, 0], "poi_sports_facility_buffer400_count": [0, 0],
    })

    result = build_leisure_enrichment(rankings, poi)

    assert result[["area_code", "leisure_poi_rank"]].values.tolist() == [["3000001", 1], ["3000002", 2]]
