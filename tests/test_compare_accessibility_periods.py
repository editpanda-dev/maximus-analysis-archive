import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from compare_accessibility_periods import combine_periods  # noqa: E402


def test_combine_periods_counts_threshold_across_hours():
    frames = {
        8: pd.DataFrame({"emdcd": [1, 2], "emdnm": ["가", "나"], "sggnm": ["구", "구"], "reachable_origin_ratio": [.8, .4]}),
        14: pd.DataFrame({"emdcd": [1, 2], "emdnm": ["가", "나"], "sggnm": ["구", "구"], "reachable_origin_ratio": [.7, .6]}),
        19: pd.DataFrame({"emdcd": [1, 2], "emdnm": ["가", "나"], "sggnm": ["구", "구"], "reachable_origin_ratio": [.9, .7]}),
    }
    result = combine_periods(frames, threshold=.5).set_index("emdcd")
    assert result.loc[1, "periods_above_threshold"] == 3
    assert result.loc[2, "periods_above_threshold"] == 2
