import pandas as pd
from scripts.audit_hanbyeol_steps1_2 import annotate_routes

def test_model_routes_do_not_claim_real_entrance_verification():
    raw=pd.DataFrame({'route_status':['inside_area','routed','assumed_straight_entrance_connector','no_route_within_700m'],
                      'walk_distance_m':[0.,300.,350.,float('nan')]})
    result=annotate_routes(raw)
    assert not result.actual_entrance_verified.any()
    assert not result.current_legal_walk_verified.any()
    assert result.walk_evidence_class.tolist()==['inside_polygon_rule_zero','osm_model_connector_le2m',
        'osm_model_assumed_connector_2_to_30m','unknown_route_or_connection']
    pd.testing.assert_series_equal(result.walk_distance_m,raw.walk_distance_m)
