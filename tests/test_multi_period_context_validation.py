import pandas as pd

from scripts.multi_period_context_validation import balanced_panel, forward_splits, group_splits


def test_balanced_panel_keeps_only_dongs_present_every_quarter():
    frame = pd.DataFrame({"admin_code": ["a", "a", "b"], "quarter": [20231, 20232, 20231]})
    out = balanced_panel(frame)
    assert set(out.admin_code) == {"a"}


def test_forward_splits_never_train_on_future_year():
    frame = pd.DataFrame({"year": [2023, 2024, 2025]})
    splits = forward_splits(frame)
    assert len(splits) == 2
    for _, train, test in splits:
        assert frame.loc[train, "year"].max() < frame.loc[test, "year"].min()


def test_group_splits_keep_each_dong_out_of_its_training_fold():
    frame = pd.DataFrame({"admin_code": ["a", "a", "b", "b", "c", "c"]})
    for _, train, test in group_splits(frame, "admin_code", n_splits=3):
        assert set(frame.loc[train, "admin_code"]).isdisjoint(set(frame.loc[test, "admin_code"]))
