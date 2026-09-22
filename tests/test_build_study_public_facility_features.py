import importlib.util
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "build_study_public_facility_features.py"
SPEC = importlib.util.spec_from_file_location("study_public", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_build_features_counts_public_facilities_only(tmp_path):
    pois = pd.DataFrame(
        [
            {"place_id": "lib", "facility_type": "public_library", "longitude": 126.98, "latitude": 37.56, "aggregation_eligible": 1, "public_access_verified": 1, "snapshot_date": "2024-01-02"},
            {"place_id": "cafe", "facility_type": "study_cafe", "longitude": 126.98, "latitude": 37.56, "aggregation_eligible": 1, "public_access_verified": 0, "snapshot_date": "2024-01-02"},
            {"place_id": "room", "facility_type": "reading_room", "longitude": 127.20, "latitude": 37.70, "aggregation_eligible": 1, "public_access_verified": 0, "snapshot_date": "2024-01-02"},
            {"place_id": "unverified-university", "facility_type": "university_learning_facility", "longitude": 126.98, "latitude": 37.56, "aggregation_eligible": 1, "public_access_verified": 0, "snapshot_date": "2024-01-02"},
        ]
    )
    poi_path = tmp_path / "pois.csv"
    pois.to_csv(poi_path, index=False)
    areas = gpd.GeoDataFrame(
        {
            "area_code": ["A"],
            "area_name": ["테스트"],
            "area_type_name": ["골목상권"],
            "minimum_period_ratio": [0.25],
            "mean_period_ratio": [0.30],
            "access_tier": ["exploration_25pct_all_periods"],
        },
        geometry=[Polygon([(126.975, 37.555), (126.985, 37.555), (126.985, 37.565), (126.975, 37.565)])],
        crs="EPSG:4326",
    )
    area_path = tmp_path / "areas.geojson"
    areas.to_file(area_path, driver="GeoJSON")
    output = tmp_path / "features.csv"

    features = MODULE.build_features(poi_path, area_path, output, 400)

    assert output.exists()
    assert len(features) == 1
    assert features.loc[0, "study_public_inside_count"] == 1
    assert features.loc[0, "study_public_all_inside_count"] == 2
    assert features.loc[0, "poi_public_library_inside_count"] == 1
    assert features.loc[0, "poi_university_learning_facility_inside_count"] == 1
    assert features.loc[0, "study_public_buffer400_count"] == 1
    assert features.loc[0, "study_public_all_buffer400_count"] == 2
    assert features.loc[0, "feature_snapshot_date"] == "2024-01-02"
