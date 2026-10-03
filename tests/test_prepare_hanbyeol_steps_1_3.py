import pandas as pd

from scripts.prepare_hanbyeol_steps_1_3 import classify_v1, validate_review


def test_bakery_transfer_does_not_change_other_industries():
    assert classify_v1("CS100005", "식사") == "카페"
    assert classify_v1("CS100010", "카페") == "카페"
    assert classify_v1("CS200038", "공부") == "공부"


def test_review_requires_documented_study_use_and_reviewer():
    row = dict(place_id="one", place_name="검토 대상", evidence_source_url="https://example.org/place",
               evidence_quote="장시간 노트북 이용 가능", seat_verified="yes", study_allowed_verified="yes",
               mandatory_purchase="unknown", reviewer="A", reviewed_at="2026-10-03",
               evidence_type="laptop_explicit", decision="s4_verified")
    assert validate_review(pd.DataFrame([row])).validation_status.item() == "reviewed"
    row["evidence_type"] = "seat_only_explicit"
    assert validate_review(pd.DataFrame([row])).validation_status.item() == "study_use_not_supported"
    row["evidence_type"] = "laptop_explicit"
    row["reviewer"] = ""
    assert validate_review(pd.DataFrame([row])).validation_status.item() == "missing_evidence_or_reviewer"
