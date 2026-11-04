import pandas as pd


def test_build_subtype_coverage_maps_each_facility_type_once_and_keeps_area_rows():
    from scripts.build_leisure_culture_subtype_coverage import build_subtype_coverage

    poi = pd.DataFrame(
        {
            "area_code": ["3000001", "3000002"],
            "area_name": ["가", "나"],
            "feature_snapshot_date": ["2026-09-16", "2026-09-16"],
            "historical_2025_use_allowed": [0, 0],
            "poi_museum_buffer400_count": [2, 0],
            "poi_art_gallery_buffer400_count": [1, 0],
            "poi_cinema_buffer400_count": [0, 1],
            "poi_exhibition_space_buffer400_count": [3, 0],
            "poi_performance_hall_buffer400_count": [4, 0],
            "poi_cultural_center_buffer400_count": [2, 0],
            "poi_park_buffer400_count": [5, 0],
            "poi_sports_facility_buffer400_count": [6, 0],
        }
    )

    area, summary = build_subtype_coverage(poi)

    assert len(area) == 2
    assert area.loc[area["area_code"] == "3000001", "viewing_exhibition_buffer400_count"].iat[0] == 6
    assert area.loc[area["area_code"] == "3000001", "performance_culture_buffer400_count"].iat[0] == 6
    assert area.loc[area["area_code"] == "3000001", "outdoor_park_buffer400_count"].iat[0] == 5
    assert area.loc[area["area_code"] == "3000001", "sports_activity_buffer400_count"].iat[0] == 6
    assert area.loc[area["area_code"] == "3000001", "leisure_subtype_total_buffer400_count"].iat[0] == 23
    assert area["historical_2025_use_allowed"].eq(False).all()
    assert set(summary["subtype_code"]) == {
        "viewing_exhibition",
        "performance_culture",
        "outdoor_park",
        "sports_activity",
    }
    assert summary.loc[summary["subtype_code"] == "viewing_exhibition", "covered_area_count"].iat[0] == 2


def test_build_subtype_coverage_rejects_duplicate_area_codes_and_missing_columns():
    from scripts.build_leisure_culture_subtype_coverage import build_subtype_coverage

    duplicate = pd.DataFrame({"area_code": ["1", "1"]})
    try:
        build_subtype_coverage(duplicate)
    except ValueError as error:
        assert "duplicate area_code" in str(error)
    else:
        raise AssertionError("duplicate area_code must fail")
