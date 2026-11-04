import copy
import pandas as pd
from shapely.geometry import Polygon, mapping, shape

from scripts.build_hanbyeol_steps6_7_20261006 import cafe_supply_rank_mask, prepare_map_layer, subtype_labels


def test_zero_cafe_count_positive_residual_is_not_supply_evidence():
    frame = pd.DataFrame({'recommendation_eligible': [True, True, True, True], 'score_status': ['supply_only', 'supply_only', 'insufficient', 'complete'], 'coffee_stores': [0, 1, 1, 1], 'bakery_stores': [0, 0, 1, 1], 'supply_only_score': [83.5, 5., 20., 30.]})
    assert cafe_supply_rank_mask(frame).tolist() == [False, True, False, False]


def test_display_topology_repair_does_not_mutate_source_geometry():
    g = Polygon([(127., 37.), (127.02, 37.02), (127., 37.02), (127.02, 37.), (127., 37.)])
    source = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': mapping(g), 'properties': {'area_code': 'A', 'area_name': 'test'}}]}
    before = copy.deepcopy(source)
    fixed, audit = prepare_map_layer(source)
    assert source == before
    assert not shape(source['features'][0]['geometry']).is_valid
    assert shape(fixed['features'][0]['geometry']).is_valid
    assert fixed['features'][0]['properties']['geometry_repaired_for_display']
    assert audit.scores_and_counts_recomputed.eq(False).all()


def test_unknown_subtype_is_not_invented_to_fill_top3():
    assert subtype_labels({'C1': 50., 'C2': float('nan')}) == 'C1'
    assert subtype_labels({'S4': float('nan')}) == 'not_available'
