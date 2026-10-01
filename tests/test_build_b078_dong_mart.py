import pandas as pd

from scripts.build_b078_dong_mart import PURPOSE_MAP, add_b078_derived_fields, parse_demographic_column


def test_move_time_is_already_minutes_and_purpose_is_mapped():
    frame = pd.DataFrame({
        "MOVE_TIME": [30], "MOVE_DIST": [12000], "MOVE_PURPOSE": [4],
        "MALE_20_CNT": [2.5], "FEML_25_CNT": [3.0],
    })
    out = add_b078_derived_fields(frame)
    assert out.loc[0, "move_time_min"] == 30
    assert out.loc[0, "purpose_name"] == "쇼핑"
    assert out.loc[0, "movement_total"] == 5.5


def test_parse_demographic_column():
    assert parse_demographic_column("MALE_20_CNT") == ("남성", "20대")
    assert parse_demographic_column("FEML_65_CNT") == ("여성", "60대이상")
    assert parse_demographic_column("MOVE_TIME") is None


def test_official_purpose_codes_are_complete():
    assert PURPOSE_MAP == {1: "출근", 2: "등교", 3: "귀가", 4: "쇼핑", 5: "관광", 6: "병원", 7: "기타"}
