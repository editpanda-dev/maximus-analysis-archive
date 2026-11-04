import numpy as np
import pandas as pd
import pytest

from scripts.build_hanbyeol_steps3_5_20261006 import (
    positive_percentile, study_components, weighted_count, stable_rank,
)


def test_unknown_counts_stay_unknown_and_observed_zero_stays_zero():
    result = positive_percentile(pd.Series([np.nan, 0., 2., 2., 4.]))
    assert np.isnan(result.iloc[0])
    assert result.iloc[1] == 0
    assert result.iloc[2] == result.iloc[3] == 50
    assert result.iloc[4] == 100
    with pytest.raises(ValueError):
        positive_percentile(pd.Series([-1., 0.]))


def test_transit_alone_cannot_produce_study_recommendation():
    result = study_components(pd.Series([0., 1., np.nan]), pd.Series([0., 0., 1.]), pd.Series([100., 100., 100.]))
    assert np.isnan(result.study_v0_score.iloc[0])
    assert np.isnan(result.study_v0_score.iloc[2])
    assert result.study_v0_score.iloc[1] == pytest.approx(60 + 100 * .10 / .75)


def test_inside_common_rule_excludes_all_external_and_unknown_routes():
    routes = pd.DataFrame([
        {'area_code': 'A', 'place_id': '1', 'route_status': 'inside_area', 'proxy_walk_access_400': True, 'walk_access_400': True},
        {'area_code': 'A', 'place_id': '2', 'route_status': 'routed', 'proxy_walk_access_400': True, 'walk_access_400': True},
        {'area_code': 'A', 'place_id': '3', 'route_status': 'assumed_straight_entrance_connector', 'proxy_walk_access_400': True, 'walk_access_400': pd.NA},
        {'area_code': 'A', 'place_id': '4', 'route_status': 'no_route_within_700m', 'proxy_walk_access_400': pd.NA, 'walk_access_400': pd.NA},
    ])
    ids = {'1', '2', '3', '4'}
    assert weighted_count(routes, ids, ['A', 'B'], 400, .25, 'inside_only').to_dict() == {'A': 1., 'B': 0.}
    assert weighted_count(routes, ids, ['A'], 400, .25, 'osm_model_le2m')['A'] == 1.25
    assert weighted_count(routes, ids, ['A'], 400, .25, 'osm_assumed_connector_proxy')['A'] == 1.5


def test_ranks_drop_missing_and_break_ties_by_area_code():
    result = stable_rank(pd.DataFrame({'area_code': ['B', 'A', 'C'], 'score': [90., 90., np.nan]}), 'score')
    assert result.area_code.tolist() == ['A', 'B']
    assert result['rank'].tolist() == [1, 2]
