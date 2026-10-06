"""Label route evidence without changing distances, flags, weights or scores."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/processed/cafe_study_taxonomy/steps1_2_20261006'
WALK=ROOT/'data/processed/cafe_study_taxonomy/osm_walk_20261002'

CLASSES={
    'inside_area':'inside_polygon_rule_zero',
    'routed':'osm_model_connector_le2m',
    'assumed_straight_entrance_connector':'osm_model_assumed_connector_2_to_30m',
    'no_route_within_700m':'unknown_route_or_connection',
    'no_pedestrian_edge_within_30m':'unknown_route_or_connection',
    'no_network_boundary_entry':'unknown_route_or_connection',
}

def annotate_routes(routes):
    out=routes.copy()
    if not set(out.route_status)<=set(CLASSES):raise ValueError('Unmapped route status')
    out['walk_evidence_class']=out.route_status.map(CLASSES)
    out['actual_entrance_verified']=False
    out['current_legal_walk_verified']=False
    out['distance_scope']='official_area_boundary_to_facility_coordinate_OSM_estimate'
    out['walk_distance_available']=out.walk_distance_m.notna()
    return out

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    raw=pd.read_csv(WALK/'walk_network_area_poi_access.csv',dtype={'area_code':str,'place_id':str})
    out=annotate_routes(raw)
    for col in raw:pd.testing.assert_series_equal(raw[col],out[col])
    assert len(out)==10132 and not out.duplicated(['area_code','place_id']).any()
    model=out.route_status.isin(['inside_area','routed'])
    assumed=out.route_status.eq('assumed_straight_entrance_connector')
    unknown=~(model|assumed)
    assert (model.sum(),assumed.sum(),unknown.sum())==(921,7165,2046)
    assert out.loc[unknown,'walk_distance_m'].isna().all()
    assert out.loc[~model,['walk_access_400','walk_access_500','walk_access_600']].isna().all().all()
    assert not out.actual_entrance_verified.any()
    out.to_csv(OUT/'walk_evidence_labels_10132.csv',index=False,encoding='utf-8-sig')
    coverage=out.groupby('area_code').agg(candidate_pairs_euclidean_600=('place_id','size'))
    for name,mask in [('inside_polygon_count',out.route_status.eq('inside_area')),
                       ('osm_model_le2m_count',out.route_status.eq('routed')),
                       ('assumed_connector_count',assumed),('unknown_connection_count',unknown)]:
        coverage[name]=out[mask].groupby('area_code').size().reindex(coverage.index,fill_value=0)
    areas=pd.read_csv(ROOT/'data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.csv',dtype={'area_code':str})
    coverage=areas[['area_code','area_name']].merge(coverage,on='area_code',how='left',validate='one_to_one')
    nums=list(coverage.columns[2:]);coverage[nums]=coverage[nums].fillna(0).astype(int)
    coverage['zero_candidates_means']='zero_in_source_candidate_set_not_verified_no_facilities'
    assert len(coverage)==coverage.area_code.nunique()==786
    assert coverage.candidate_pairs_euclidean_600.sum()==10132
    old=pd.read_csv(WALK/'walk_route_area_coverage_786.csv',dtype={'area_code':str})
    previous=OUT/'coverage_denominator_correction_786.csv'
    legacy=old[['area_code','candidate_pairs_euclidean_600']]
    if previous.exists():
        legacy=pd.read_csv(previous,dtype={'area_code':str})[['area_code','candidate_pairs_euclidean_600_legacy']].rename(
            columns={'candidate_pairs_euclidean_600_legacy':'candidate_pairs_euclidean_600'})
    comparison=coverage[['area_code','candidate_pairs_euclidean_600']].merge(
        legacy,on='area_code',suffixes=('_corrected','_legacy'))
    comparison['overcount_in_legacy_search']=comparison.candidate_pairs_euclidean_600_legacy-comparison.candidate_pairs_euclidean_600_corrected
    assert comparison.overcount_in_legacy_search.ge(0).all()
    comparison.to_csv(OUT/'coverage_denominator_correction_786.csv',index=False,encoding='utf-8-sig')
    coverage.to_csv(OUT/'walk_evidence_coverage_786.csv',index=False,encoding='utf-8-sig')
    # Correct metadata only; historical route lengths and inclusion flags stay unchanged.
    fixed=old.drop(columns=['candidate_pairs_euclidean_600']).merge(
        coverage[['area_code','candidate_pairs_euclidean_600']],on='area_code',validate='one_to_one')
    fixed.to_csv(WALK/'walk_route_area_coverage_786.csv',index=False,encoding='utf-8-sig')
    sensitivity=pd.read_csv(WALK/'walk_radius_sensitivity.csv')
    sensitivity['method']=sensitivity.method.replace({'verified_connector_le2m':'osm_model_connector_le2m'})
    sensitivity.to_csv(WALK/'walk_radius_sensitivity.csv',index=False,encoding='utf-8-sig')
    report={'rows':len(out),'areas':len(coverage),'inside':813,'osm_model_le2m':108,
            'assumed_connector':7165,'unknown_connection':2046,
            'legacy_candidate_total':int(comparison.candidate_pairs_euclidean_600_legacy.sum()),
            'corrected_candidate_total':10132,'legacy_overcount':int(comparison.overcount_in_legacy_search.sum()),
            'distance_and_flags_unchanged':True,'actual_entrances_not_verified':True,
            'windows_environment_lock_status':'received_exact_26_versions_windows_pip_check_passed_user_reported',
            'study_decision':'S4_excluded_v0_approved_not_reweighted_in_steps1_2'}
    (OUT/'steps1_2_qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':build()
