"""S4-excluded exploratory facility baseline and separate observed cafe ranks.

Uses committed snapshots only. No API calls, entrance claims or sales imputation.
Three-purpose common spatial comparison is inside-only supply, NOT a replacement
for the team purpose scores or a completed network-distance recommendation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/cafe_study_taxonomy/steps3_5_20261006'
SNAP = ROOT / 'data/external/team_branch_snapshots'
WEIGHTS = {'study_cafe': .45 / .75, 'public': .20 / .75, 'transit': .10 / .75}


def positive_percentile(values: pd.Series) -> pd.Series:
    """Observed zero stays zero; missing stays missing, including in ranks."""
    numbers = pd.to_numeric(values, errors='raise')
    if numbers.dropna().lt(0).any():
        raise ValueError('Negative facility counts are invalid')
    result = pd.Series(np.nan, index=numbers.index, dtype=float)
    result.loc[numbers.eq(0)] = 0.
    positive = numbers.gt(0)
    result.loc[positive] = numbers.loc[positive].rank(method='average', pct=True) * 100
    return result


def weighted_count(routes, ids, codes, radius, weight, method):
    if method == 'inside_only':
        chosen = routes.loc[routes.place_id.isin(ids) & routes.route_status.eq('inside_area')]
    else:
        prefix = 'proxy_walk_access_' if method == 'osm_assumed_connector_proxy' else 'walk_access_'
        chosen = routes.loc[routes.place_id.isin(ids) & routes[prefix + str(radius)].eq(True)]
    inside = chosen.loc[chosen.route_status.eq('inside_area')].groupby('area_code').place_id.nunique()
    outside = chosen.loc[~chosen.route_status.eq('inside_area')].groupby('area_code').place_id.nunique()
    # Zero is a count within the included source/model rule, never verified absence.
    return pd.Series({code: inside.get(code, 0) + weight * outside.get(code, 0) for code in codes})


def study_components(study, public, transit):
    out = pd.DataFrame(index=study.index)
    out['study_cafe_contribution'] = WEIGHTS['study_cafe'] * positive_percentile(study)
    out['public_contribution'] = WEIGHTS['public'] * positive_percentile(public)
    out['transit_contribution'] = WEIGHTS['transit'] * transit
    score = out.sum(axis=1, min_count=3)
    # Transit alone cannot make a study destination. No observed supply is insufficient.
    out['study_v0_score'] = score.where((study + public).gt(0))
    return out


def stable_rank(frame, score):
    ranked = frame.loc[frame[score].notna()].sort_values([score, 'area_code'], ascending=[False, True]).copy()
    ranked.insert(0, 'rank', np.arange(1, len(ranked) + 1))
    return ranked


def save(frame, name):
    frame.to_csv(OUT / name, index=False, encoding='utf-8-sig')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    cafe_path = SNAP / 'cafe_size_adjusted_786_6c591a7.csv'
    meal_path = SNAP / 'food_shopping_v1_786_13e42d2.csv'
    routes_path = ROOT / 'data/processed/cafe_study_taxonomy/steps1_2_20261006/walk_evidence_labels_10132.csv'
    public_path = ROOT / 'data/external/study_public_facility_poi.csv'
    kakao_path = ROOT / 'data/external/kakao_study_stay_pois_20260918.csv'
    cafe = pd.read_csv(cafe_path, dtype={'area_code': str})
    meal = pd.read_csv(meal_path, dtype={'area_code': str})
    routes = pd.read_csv(routes_path, dtype={'area_code': str, 'place_id': str})
    public = pd.read_csv(public_path, dtype={'place_id': str})
    kakao = pd.read_csv(kakao_path, dtype={'place_id': str})
    coverage = pd.read_csv(ROOT / 'data/processed/cafe_study_taxonomy/steps1_2_20261006/walk_evidence_coverage_786.csv', dtype={'area_code': str})
    for source in (cafe, meal, coverage):
        assert len(source) == source.area_code.nunique() == 786
    assert set(cafe.area_code) == set(meal.area_code) == set(coverage.area_code)
    assert len(routes) == 10132 and not routes.duplicated(['area_code', 'place_id']).any()
    cafe = cafe.sort_values('area_code').reset_index(drop=True)
    codes = cafe.area_code.tolist()
    transit = cafe.set_index('area_code').access_percentile.reindex(codes)
    assert transit.notna().all() and transit.between(0, 100).all()
    study_ids = set('kakao:' + kakao.loc[kakao.place_type.eq('study_cafe'), 'place_id'])
    public_filter = public.public_access_verified.eq(1) & public.study_access_verified.eq(1) & public.facility_type.isin(['public_library', 'reading_room', 'youth_space'])
    public_ids = set('public:' + public.loc[public_filter & public.operation_status.ne('listed_stale_unverified'), 'place_id'])
    active_ids = set('public:' + public.loc[public_filter & public.operation_status.eq('active_page_with_hours'), 'place_id'])
    assert (len(study_ids), len(public_ids), len(active_ids)) == (852, 195, 16)
    assert not (study_ids & public_ids)
    variants = []
    for method in ('osm_assumed_connector_proxy', 'osm_model_le2m'):
        for radius in (400, 500, 600):
            for weight in (0., .25, .5):
                study = weighted_count(routes, study_ids, codes, radius, weight, method)
                pub = weighted_count(routes, public_ids, codes, radius, weight, method)
                active = weighted_count(routes, active_ids, codes, radius, weight, method)
                part = study_components(study, pub, transit)
                part['area_code'] = part.index
                part['method'] = method
                part['radius_m'] = radius
                part['nearby_weight'] = weight
                part['study_cafe_weighted_count'] = study
                part['public_weighted_count'] = pub
                part['public_hours_page_weighted_count'] = active
                part['study_v0_status'] = np.where(part.study_v0_score.notna(), 'exploratory_S4_excluded_operation_not_reverified', 'insufficient_no_included_source_facility')
                variants.append(part.reset_index(drop=True))
    variants = pd.concat(variants, ignore_index=True)
    save(variants, 'study_v0_variants_786x18.csv')
    primary = variants.loc[variants.method.eq('osm_assumed_connector_proxy') & variants.radius_m.eq(400) & variants.nearby_weight.eq(.25)].drop(columns=['method', 'radius_m', 'nearby_weight'])
    frame = cafe[['area_code', 'area_name', 'area_type_name', 'area_km2', 'total_stores_2025q4', 'recommendation_eligible', 'exclusion_reason', 'access_percentile', 'study_room_stores']].merge(primary, on='area_code', validate='one_to_one').merge(coverage.drop(columns='area_name'), on='area_code', validate='one_to_one')
    frame['S4_included'] = False
    frame['S3b_role'] = 'validation_only_not_scored'
    frame['study_version'] = 'facility_accessibility_v0_S4_excluded_OSM_entrance_proxy'
    frame['actual_entrance_verified'] = False
    frame['current_operation_verified'] = False
    frame['counts_scope'] = 'included_source_model_counts_zero_is_not_verified_absence'
    frame['study_recommendation_eligible'] = frame.recommendation_eligible & frame.study_v0_score.notna()
    frame['route_evidence_status'] = np.select([frame.candidate_pairs_euclidean_600.eq(0), frame.assumed_connector_count.gt(0), frame.unknown_connection_count.gt(0)], ['no_source_candidate_pairs', 'contains_assumed_connectors', 'contains_unresolved_connections'], default='inside_rule_or_OSM_model_only')
    # Preserve original partial components for an explicit recalibration comparison.
    frame['legacy_75pct_sum_reconstructed'] = frame[['study_cafe_contribution', 'public_contribution', 'transit_contribution']].sum(axis=1) * .75
    save(frame, 'study_facility_accessibility_v0_786.csv')
    # Diagnose size effects on the same available, eligible population; do not
    # quietly adopt a new model as the team's v0 formula.
    size_population = frame.loc[frame.study_recommendation_eligible].copy()
    size_methods = {'count_based_v0': size_population.study_v0_score}
    size_methods['density_smoothed_0.05km2_diagnostic'] = (
        WEIGHTS['study_cafe'] * positive_percentile(size_population.study_cafe_weighted_count / (size_population.area_km2 + .05))
        + WEIGHTS['public'] * positive_percentile(size_population.public_weighted_count / (size_population.area_km2 + .05))
        + WEIGHTS['transit'] * size_population.access_percentile)
    predictors = np.column_stack([np.ones(len(size_population)), np.log(size_population.area_km2), np.log1p(size_population.total_stores_2025q4)])
    assert np.isfinite(predictors).all()
    residual_score = WEIGHTS['transit'] * size_population.access_percentile
    for col, weight_key in [('study_cafe_weighted_count', 'study_cafe'), ('public_weighted_count', 'public')]:
        y = np.log1p(size_population[col].to_numpy())
        fitted = predictors @ np.linalg.lstsq(predictors, y, rcond=None)[0]
        residual = pd.Series(y - fitted, index=size_population.index)
        percentile = residual.rank(method='average', pct=True) * 100
        residual_score = residual_score + WEIGHTS[weight_key] * percentile.where(size_population[col].gt(0), 0.)
    size_methods['OLS_log_count_residual_diagnostic'] = residual_score
    base_top = set(stable_rank(size_population, 'study_v0_score').head(10).area_code)
    size_rows = []
    for method, score in size_methods.items():
        part = size_population.assign(diagnostic_score=score)
        size_rows.append({'method': method, 'common_population': len(part), 'area_spearman': part.diagnostic_score.corr(part.area_km2, method='spearman'), 'total_stores_spearman': part.diagnostic_score.corr(part.total_stores_2025q4, method='spearman'), 'top10_overlap_vs_count_v0': len(base_top & set(stable_rank(part, 'diagnostic_score').head(10).area_code)) / 10, 'adoption_status': 'v0_current_count_baseline' if method == 'count_based_v0' else 'diagnostic_only_not_adopted'})
    save(pd.DataFrame(size_rows), 'study_size_effect_diagnostics.csv')
    study_rank = stable_rank(frame.loc[frame.study_recommendation_eligible], 'study_v0_score')
    study_rank['ranking_universe_count'] = len(study_rank)
    study_rank['evidence_sentence'] = ('스터디카페 가중 집계 ' + study_rank.study_cafe_weighted_count.round(2).astype(str) + ', 공개 학습시설 가중 집계 ' + study_rank.public_weighted_count.round(2).astype(str) + '; 내부 + OSM 잠정400m 외부25%, S4 제외. 실제 출입구·현재 운영 미검증')
    save(study_rank, 'study_v0_ranking_available.csv')
    save(study_rank.head(10), 'study_v0_top10.csv')
    save(study_rank.head(20), 'study_v0_top20.csv')

    comparisons = []
    for method in variants.method.unique():
        reference = variants.loc[variants.method.eq(method) & variants.radius_m.eq(400) & variants.nearby_weight.eq(.25)]
        for (radius, weight), part in variants.loc[variants.method.eq(method)].groupby(['radius_m', 'nearby_weight']):
            joined = reference[['area_code', 'study_v0_score']].merge(part[['area_code', 'study_v0_score']], on='area_code', suffixes=('_base', '_variant')).merge(cafe[['area_code', 'recommendation_eligible']], on='area_code')
            common = joined.loc[joined.recommendation_eligible & joined.study_v0_score_base.notna() & joined.study_v0_score_variant.notna()]
            own_base = reference.merge(cafe[['area_code', 'recommendation_eligible']], on='area_code')
            own_part = part.merge(cafe[['area_code', 'recommendation_eligible']], on='area_code')
            own_a = stable_rank(own_base.loc[own_base.recommendation_eligible], 'study_v0_score').head(10)
            own_b = stable_rank(own_part.loc[own_part.recommendation_eligible], 'study_v0_score').head(10)
            comparisons.append({'method': method, 'radius_m': radius, 'nearby_weight': weight, 'common_observed_population': len(common), 'rank_spearman_common': common.study_v0_score_base.corr(common.study_v0_score_variant, method='spearman'), 'top10_overlap_each_available_population': len(set(own_a.area_code) & set(own_b.area_code)) / min(len(own_a), len(own_b)) if min(len(own_a), len(own_b)) else np.nan, 'base_population': int(own_base.loc[own_base.recommendation_eligible, 'study_v0_score'].notna().sum()), 'variant_population': int(own_part.loc[own_part.recommendation_eligible, 'study_v0_score'].notna().sum())})
    save(pd.DataFrame(comparisons), 'study_v0_radius_weight_sensitivity.csv')

    # Retain the latest cafe residual draft as an explicitly provisional version.
    cafe_out = cafe[['area_code', 'area_name', 'area_type_name', 'recommendation_eligible', 'exclusion_reason', 'coffee_stores', 'bakery_stores', 'total_stores_2025q4', 'coffee_sales_observed', 'bakery_sales_observed', 'score_status', 'score_status_reason']].copy()
    cafe_out['full_score'] = cafe.cafe_size_adjusted_full_score.where(cafe.score_status.eq('complete'))
    cafe_out['supply_only_score'] = cafe.cafe_size_adjusted_supply_only_score.where(cafe.score_status.eq('supply_only'))
    cafe_out['legacy_full_score'] = cafe.full_score.where(cafe.score_status.eq('complete'))
    cafe_out['score_version'] = '6c591a7_residual_size_adjusted_draft_2025Q4'
    cafe_out['spatial_basis'] = 'official_inside_counts_no_external_walk_component'
    cafe_out['ranking_universe'] = cafe_out.score_status.map({'complete': 'complete_sales_observed_only', 'supply_only': 'supply_only_exploration_only', 'insufficient': 'not_ranked'})
    save(cafe_out, 'cafe_observation_separated_786.csv')
    cafe_ranks = {}
    for status, score in [('complete', 'full_score'), ('supply_only', 'supply_only_score')]:
        group = stable_rank(cafe_out.loc[cafe_out.recommendation_eligible & cafe_out.score_status.eq(status)], score)
        group['ranking_universe_count'] = len(group)
        group['ranking_status'] = 'observed_group_provisional' if status == 'complete' else 'supply_only_exploration_separate_rank'
        cafe_ranks[status] = group
        save(group, f'cafe_{status}_ranking.csv')
        save(group.head(10), f'cafe_{status}_top10.csv')
        save(group.head(20), f'cafe_{status}_top20.csv')
    save(cafe_out.loc[cafe_out.score_status.eq('insufficient')], 'cafe_insufficient_unranked.csv')
    summary = cafe_out.groupby('score_status').agg(analysis_area_count=('area_code', 'size'), recommendation_area_count=('recommendation_eligible', 'sum')).reset_index()
    save(summary, 'cafe_population_summary.csv')

    # Same polygon (verified identical Git blob), all purposes ONLY inside, no
    # 400m external features and no consumption signal. Versions remain separate.
    common = cafe[['area_code', 'area_name', 'area_km2', 'recommendation_eligible', 'cafe_stores']].merge(meal[['area_code', 'food_inside_count', 'food_eligible', 'food_sales_status', 'walk_distance_basis']], on='area_code', validate='one_to_one')
    inside_study = weighted_count(routes, study_ids, codes, 400, 0, 'inside_only')
    inside_public = weighted_count(routes, public_ids, codes, 400, 0, 'inside_only')
    common['study_cafe_inside_source_count'] = common.area_code.map(inside_study)
    common['public_inside_source_count'] = common.area_code.map(inside_public)
    common['inside_density_denominator_km2'] = common.area_km2 + .05
    for purpose, counts in [('meal', common.food_inside_count), ('cafe', common.cafe_stores)]:
        common[purpose + '_inside_supply_score'] = positive_percentile(counts / common.inside_density_denominator_km2).where(counts.gt(0))
    common['study_inside_supply_score'] = (.45 * positive_percentile(common.study_cafe_inside_source_count / common.inside_density_denominator_km2) + .20 * positive_percentile(common.public_inside_source_count / common.inside_density_denominator_km2)) / .65
    common['study_inside_supply_score'] = common.study_inside_supply_score.where((common.study_cafe_inside_source_count + common.public_inside_source_count).gt(0))
    common['common_distance_basis'] = 'same_official_polygon_inside_only_zero_m_no_external_facilities'
    common['comparison_status'] = 'supply_only_diagnostic_not_team_full_scores'
    common['source_periods'] = 'meal_SBIZ_2026_06_cafe_official_2025Q4_study_POI_2026_09'
    eligible = common.recommendation_eligible & common.food_eligible & common[['meal_inside_supply_score', 'cafe_inside_supply_score', 'study_inside_supply_score']].notna().all(axis=1)
    combo = common.loc[eligible].copy()
    for purpose in ('meal', 'cafe', 'study'):
        combo[purpose + '_percentile_common'] = combo[purpose + '_inside_supply_score'].rank(method='average', pct=True) * 100
    combo['three_purpose_inside_supply_comparison_score'] = combo[['meal_percentile_common', 'cafe_percentile_common', 'study_percentile_common']].mean(axis=1)
    combo = stable_rank(combo, 'three_purpose_inside_supply_comparison_score')
    combo['ranking_universe_count'] = len(combo)
    save(common, 'common_inside_supply_features_786.csv')
    save(combo, 'three_purpose_inside_supply_comparison_ranking.csv')
    save(combo.head(10), 'three_purpose_inside_supply_comparison_top10.csv')
    save(combo.head(20), 'three_purpose_inside_supply_comparison_top20.csv')
    cafe_study = common.loc[common.recommendation_eligible & common[['cafe_inside_supply_score', 'study_inside_supply_score']].notna().all(axis=1)].copy()
    for purpose in ('cafe', 'study'):
        cafe_study[purpose + '_percentile_common'] = cafe_study[purpose + '_inside_supply_score'].rank(method='average', pct=True) * 100
    cafe_study['two_purpose_inside_supply_comparison_score'] = cafe_study[['cafe_percentile_common', 'study_percentile_common']].mean(axis=1)
    cafe_study = stable_rank(cafe_study, 'two_purpose_inside_supply_comparison_score')
    cafe_study['ranking_universe_count'] = len(cafe_study)
    save(cafe_study.head(10), 'cafe_study_inside_supply_comparison_top10.csv')
    save(cafe_study.head(20), 'cafe_study_inside_supply_comparison_top20.csv')
    contract = pd.DataFrame([
        {'purpose': 'meal_latest_team_score', 'input_commit': '13e42d27124f262f08eea4deeb50a8583fc4a871', 'distance_basis': 'euclidean_400m_buffer', 'external_included': True, 'common_network_ready': False},
        {'purpose': 'cafe_latest_draft', 'input_commit': '6c591a7a23a78cbbf0bff574e27346bd9ee7ff68', 'distance_basis': 'official_inside_counts_no_external_walk_component', 'external_included': False, 'common_network_ready': False},
        {'purpose': 'study_v0', 'input_commit': '1a69e28_local_route_labels', 'distance_basis': 'OSM_400m_assumed_connector_proxy_nearby_weight_0.25', 'external_included': True, 'common_network_ready': False},
        {'purpose': 'three_purpose_inside_supply_comparison', 'input_commit': 'derived_from_above', 'distance_basis': 'same_polygon_inside_only', 'external_included': False, 'common_network_ready': False},
    ])
    save(contract, 'cross_purpose_distance_contract.csv')
    pd.DataFrame([{'requested_output': 'three_purpose_network_based_final_score', 'status': 'BLOCKED_COMMON_NETWORK_INPUT', 'required': 'SBIZ full point source; area-cell route cache; consistent polygon-boundary/entrance policy; no silent Euclidean fallback'}]).to_csv(OUT / 'network_combination_status.csv', index=False, encoding='utf-8-sig')

    checks = [
        ('786_unique_codes_all_outputs', all(len(x) == x.area_code.nunique() == 786 for x in [frame, cafe_out, common])),
        ('variant_rows_18x786', len(variants) == 18 * 786),
        ('no_S4_or_S3b_in_score', not frame.S4_included.any() and frame.S3b_role.eq('validation_only_not_scored').all()),
        ('weights_sum_one', np.isclose(sum(WEIGHTS.values()), 1)),
        ('study_score_range', frame.study_v0_score.dropna().between(0, 100).all()),
        ('study_components_equal_score', np.allclose(frame.loc[frame.study_v0_score.notna(), ['study_cafe_contribution', 'public_contribution', 'transit_contribution']].sum(axis=1), frame.loc[frame.study_v0_score.notna(), 'study_v0_score'])),
        ('no_transit_only_study_rank', ((study_rank.study_cafe_weighted_count + study_rank.public_weighted_count) > 0).all()),
        ('no_actual_entrance_claim', not frame.actual_entrance_verified.any()),
        ('model_flag_unknown_for_assumed_routes', routes.loc[routes.route_status.eq('assumed_straight_entrance_connector'), ['walk_access_400', 'walk_access_500', 'walk_access_600']].isna().all().all()),
        ('cafe_status_counts', cafe_out.score_status.value_counts().to_dict() == {'insufficient': 330, 'supply_only': 232, 'complete': 224}),
        ('cafe_complete_only_scores', cafe_out.loc[~cafe_out.score_status.eq('complete'), 'full_score'].isna().all() and cafe_out.full_score.notna().sum() == 224),
        ('cafe_complete_both_sales_observed', cafe_out.loc[cafe_out.score_status.eq('complete'), ['coffee_sales_observed', 'bakery_sales_observed']].eq(True).all().all()),
        ('cafe_supply_only_separate_scores', cafe_out.loc[~cafe_out.score_status.eq('supply_only'), 'supply_only_score'].isna().all() and cafe_out.supply_only_score.notna().sum() == 232),
        ('cafe_insufficient_not_ranked', set(cafe_ranks['complete'].area_code).isdisjoint(cafe_ranks['supply_only'].area_code)),
        ('cafe_score_ranges', all(cafe_out[col].dropna().between(0, 100).all() for col in ['full_score', 'supply_only_score'])),
        ('cafe_rank_population_sizes', len(cafe_ranks['complete']) == 218 and len(cafe_ranks['supply_only']) == 232),
        ('no_tourism_ranked', study_rank.recommendation_eligible.all() and combo.recommendation_eligible.all()),
        ('latest_meal_basis_audited', meal.walk_distance_basis.eq('euclidean_400m_buffer').all()),
        ('common_features_inside_only', common.common_distance_basis.eq('same_official_polygon_inside_only_zero_m_no_external_facilities').all()),
        ('combo_equal_weight_common_population', combo[['meal_percentile_common', 'cafe_percentile_common', 'study_percentile_common']].notna().all().all() and np.allclose(combo.three_purpose_inside_supply_comparison_score, combo[['meal_percentile_common', 'cafe_percentile_common', 'study_percentile_common']].mean(axis=1))),
        ('route_source_counts_preserved', routes.route_status.value_counts().to_dict() == {'assumed_straight_entrance_connector': 7165, 'no_route_within_700m': 1511, 'inside_area': 813, 'no_pedestrian_edge_within_30m': 529, 'routed': 108, 'no_network_boundary_entry': 6}),
    ]
    qa = pd.DataFrame([{'check': name, 'status': 'PASS' if bool(ok) else 'FAIL'} for name, ok in checks])
    save(qa, 'steps3_5_qa.csv')
    assert qa.status.eq('PASS').all(), qa.to_string(index=False)
    inputs = []
    for path in [cafe_path, meal_path, routes_path, public_path, kakao_path]:
        inputs.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    report = {'version': '20261006_steps3_5', 'study_weights': WEIGHTS, 'S4_excluded': True, 'S3b_scored': False, 'public_source_eligible': 195, 'public_hours_page_source': 16, 'public_standard_listing_operation_unverified': 179, 'study_score_available': int(frame.study_v0_score.notna().sum()), 'study_recommendation_population': len(study_rank), 'cafe_analysis_status_counts': cafe_out.score_status.value_counts().to_dict(), 'cafe_complete_recommendation_population': len(cafe_ranks['complete']), 'cafe_supply_only_population': len(cafe_ranks['supply_only']), 'three_purpose_inside_supply_population': len(combo), 'cafe_study_inside_supply_population': len(cafe_study), 'network_combination_status': 'BLOCKED_COMMON_NETWORK_INPUT', 'polygon_git_blob_both_inputs': '47861bb84c1190a6221e5baa22295f63b85a40c2', 'qa_pass': len(qa), 'inputs': inputs}
    (OUT / 'steps3_5_summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'inputs'}, ensure_ascii=False))
    return report


if __name__ == '__main__':
    build()
