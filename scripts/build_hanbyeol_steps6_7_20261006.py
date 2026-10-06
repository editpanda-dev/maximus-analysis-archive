"""Current baseline ranks, explanations and maps; no new routing or API calls."""
from __future__ import annotations

import copy
import hashlib
import html
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely import make_valid
from shapely.validation import explain_validity
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/processed/cafe_study_taxonomy/steps3_5_20261006'
OUT = ROOT / 'data/processed/cafe_study_taxonomy/steps6_7_20261006'


def cafe_supply_rank_mask(frame):
    """An inherited positive residual is not evidence of any cafe supply."""
    return (frame.recommendation_eligible.eq(True) & frame.score_status.eq('supply_only')
            & (frame.coffee_stores + frame.bakery_stores).gt(0) & frame.supply_only_score.notna())


def rank(frame, score):
    result = frame.loc[frame[score].notna()].sort_values([score, 'area_code'], ascending=[False, True]).copy()
    result.insert(0, 'rank', range(1, len(result) + 1))
    result['ranking_universe_count'] = len(result)
    return result


def subtype_labels(scores):
    observed = [(name, float(value)) for name, value in scores.items() if pd.notna(value)]
    observed.sort(key=lambda v: (-v[1], v[0]))
    return '|'.join(name for name, _ in observed[:3]) or 'not_available'


def prepare_map_layer(source):
    """Repair display topology on a copy; source polygons and scores stay intact."""
    layer = copy.deepcopy(source)
    audit = []
    converter = Transformer.from_crs(4326, 5186, always_xy=True).transform
    for feature in layer['features']:
        original = shape(feature['geometry'])
        repaired = not original.is_valid
        feature['properties']['geometry_repaired_for_display'] = repaired
        if repaired:
            valid = make_valid(original)
            if valid.geom_type not in ('Polygon', 'MultiPolygon') or not valid.is_valid or valid.is_empty:
                raise ValueError('Unusable map polygon after topology repair')
            original_area = transform(converter, original).area
            repaired_area = transform(converter, valid).area
            audit.append({'area_code': str(feature['properties']['area_code']), 'area_name': feature['properties']['area_name'], 'source_validity_problem': explain_validity(original), 'method': 'Shapely_make_valid_display_only', 'original_projected_area_m2': original_area, 'repaired_projected_area_m2': repaired_area, 'area_change_m2': repaired_area-original_area, 'scores_and_counts_recomputed': False})
            feature['geometry'] = mapping(valid)
        assert shape(feature['geometry']).is_valid and not shape(feature['geometry']).is_empty
    return layer, pd.DataFrame(audit)


def save(frame, name):
    frame.to_csv(OUT / name, index=False, encoding='utf-8-sig')


def svg_map(layer, ranked, title, population):
    """Standalone projected polygon map with Top20 markers, no online basemap."""
    converter = Transformer.from_crs(4326, 5186, always_xy=True).transform
    geometries = {str(f['properties']['area_code']): transform(converter, shape(f['geometry'])) for f in layer['features']}
    bounds = np.array([g.bounds for g in geometries.values()])
    xmin, ymin = bounds[:, 0].min(), bounds[:, 1].min()
    xmax, ymax = bounds[:, 2].max(), bounds[:, 3].max()
    scale = min(890 / (xmax - xmin), 690 / (ymax - ymin))
    xy = lambda x, y: (35 + (x - xmin) * scale, 110 + (ymax - y) * scale)
    top = {r.area_code: int(r.rank) for r in ranked.head(20).itertuples()}
    chunks = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="860" viewBox="0 0 1440 860"><rect width="1440" height="860" fill="white"/><g font-family="Malgun Gothic, Noto Sans CJK KR, sans-serif"><text x="35" y="35" font-size="23">{html.escape(title)}</text><text x="35" y="65" font-size="14">비교 집단 {population}개 · 공식 상권 786개 보존 · Top20 표시</text><text x="35" y="88" font-size="13">탐색 기준선 / 실제 출입구·현재 운영 미검증 / 외부 배경지도 사용 없음</text>']
    for code, g in sorted(geometries.items(), key=lambda item: -item[1].area):
        parts = list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]
        paths = []
        for polygon in parts:
            for ring in [polygon.exterior, *polygon.interiors]:
                points = [xy(x, y) for x, y in ring.coords]
                paths.append('M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in points) + ' Z')
        fill = '#c33c54' if code in top else '#e6e8eb'
        chunks.append(f'<path d="{" ".join(paths)}" fill="{fill}" fill-rule="evenodd" stroke="#a2a8b0" stroke-width="0.45"><title>{html.escape(code)}</title></path>')
    for row in ranked.head(20).itertuples():
        point = geometries[row.area_code].representative_point()
        x, y = xy(point.x, point.y)
        chunks.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="10" fill="#173c66"/><text x="{x:.2f}" y="{y+4:.2f}" text-anchor="middle" font-size="11" fill="white">{row.rank}</text>')
        chunks.append(f'<text x="965" y="{135 + (row.rank-1)*29}" font-size="14">{row.rank}. {html.escape(row.area_name)}</text>')
    chunks.append('<text x="35" y="825" font-size="12">폴리곤: 서울 공식 상권 · 공부 경로: OSM/Geofabrik 2026-10-02, © OpenStreetMap contributors / ODbL</text></g></svg>')
    return ''.join(chunks)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    cafe_path = SOURCE / 'cafe_observation_separated_786.csv'
    study_path = SOURCE / 'study_facility_accessibility_v0_786.csv'
    common_path = SOURCE / 'common_inside_supply_features_786.csv'
    geo_path = ROOT / 'data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson'
    subtype_path = ROOT / 'data/external/team_branch_snapshots/cafe_size_adjusted_786_6c591a7.csv'
    cafe = pd.read_csv(cafe_path, dtype={'area_code': str})
    study = pd.read_csv(study_path, dtype={'area_code': str})
    common = pd.read_csv(common_path, dtype={'area_code': str})
    subtypes = pd.read_csv(subtype_path, dtype={'area_code': str})
    source_layer = json.loads(geo_path.read_text())
    layer, geometry_audit = prepare_map_layer(source_layer)
    save(geometry_audit, 'polygon_display_repair_audit_4.csv')
    for frame in (cafe, study, common, subtypes):
        assert len(frame) == frame.area_code.nunique() == 786
    codes = set(cafe.area_code)
    assert all(set(f.area_code) == codes for f in (study, common, subtypes))
    assert len(layer['features']) == 786 and {str(f['properties']['area_code']) for f in layer['features']} == codes
    assert all(shape(f['geometry']).is_valid and not shape(f['geometry']).is_empty for f in layer['features'])

    excluded = cafe.loc[cafe.score_status.eq('supply_only') & (cafe.coffee_stores + cafe.bakery_stores).eq(0)].copy()
    excluded['correction_reason'] = 'zero_source_cafe_supply_positive_residual_not_ranking_evidence'
    save(excluded, 'cafe_zero_supply_rank_correction_48.csv')
    cafe['legacy_supply_only_score_before_rank_guard'] = cafe.supply_only_score
    cafe['cafe_supply_rank_eligible'] = cafe_supply_rank_mask(cafe)
    cafe['cafe_complete_rank_eligible'] = cafe.recommendation_eligible & cafe.score_status.eq('complete') & (cafe.coffee_stores + cafe.bakery_stores).gt(0) & cafe.full_score.notna()
    cafe['supply_only_score'] = cafe.supply_only_score.where(cafe.cafe_supply_rank_eligible)
    cafe['ranking_exclusion_reason'] = np.select([~cafe.recommendation_eligible, cafe.score_status.eq('supply_only') & (cafe.coffee_stores + cafe.bakery_stores).eq(0), cafe.score_status.eq('insufficient')], ['broad_tourism_reference', 'no_cafe_supply_in_source_snapshot', 'insufficient_sales_evidence'], default='')
    cafe = cafe.merge(subtypes[['area_code', 'coffee_size_adjusted_full_score', 'bakery_size_adjusted_full_score', 'coffee_size_adjusted_supply_score', 'bakery_size_adjusted_supply_score']], on='area_code', validate='one_to_one')
    cafe['C1_subtype_score'] = np.where(cafe.score_status.eq('complete'), cafe.coffee_size_adjusted_full_score, np.where(cafe.score_status.eq('supply_only'), cafe.coffee_size_adjusted_supply_score, np.nan))
    cafe['C2_subtype_score'] = np.where(cafe.score_status.eq('complete'), cafe.bakery_size_adjusted_full_score, np.where(cafe.score_status.eq('supply_only'), cafe.bakery_size_adjusted_supply_score, np.nan))
    cafe['C1_subtype_score'] = cafe.C1_subtype_score.where(cafe.coffee_stores.gt(0))
    cafe['C2_subtype_score'] = cafe.C2_subtype_score.where(cafe.bakery_stores.gt(0))
    cafe['C1_model_contribution'] = .7 * np.where(cafe.score_status.eq('complete'), cafe.coffee_size_adjusted_full_score, np.where(cafe.score_status.eq('supply_only'), cafe.coffee_size_adjusted_supply_score, np.nan))
    cafe['C2_model_contribution'] = .3 * np.where(cafe.score_status.eq('complete'), cafe.bakery_size_adjusted_full_score, np.where(cafe.score_status.eq('supply_only'), cafe.bakery_size_adjusted_supply_score, np.nan))
    cafe['cafe_top3_available_subtypes'] = cafe.apply(lambda r: subtype_labels({'C1_coffee': r.C1_subtype_score, 'C2_bakery': r.C2_subtype_score}), axis=1)
    cafe['cafe_best_available_subtype'] = cafe.cafe_top3_available_subtypes.str.split('|').str[0]
    cafe['subtype_status'] = 'only_C1_C2_available_C_stay_unverified_no_third_subtype'
    cafe['cafe_evidence_sentence'] = cafe.apply(lambda r: f"공식 2025Q4 커피·음료 {int(r.coffee_stores)}개, 제과 {int(r.bakery_stores)}개. 매출 상태 {r.score_status}; " + ('공급·소비 완전관측군의 잔차 보정 초안.' if r.cafe_complete_rank_eligible else '공급 전용 탐색군.' if r.cafe_supply_rank_eligible else f'순위 제외: {r.ranking_exclusion_reason}.') + ' 현재 영업·체류·학습 허용 미검증.', axis=1)
    save(cafe, 'cafe_guarded_scorecard_786.csv')

    study['S_study_cafe_source_score'] = study.study_cafe_contribution / .6
    study['S_public_source_score'] = study.public_contribution / (.2 / .75)
    study['study_available_facility_signal_order'] = study.apply(lambda r: subtype_labels({'paid_study_cafe_source': r.S_study_cafe_source_score if r.study_cafe_weighted_count > 0 else np.nan, 'public_learning_source': r.S_public_source_score if r.public_weighted_count > 0 else np.nan}), axis=1)
    study['study_subtype_status'] = 'two_source_facility_signals_only_not_verified_activity_subtypes_S4_excluded'
    study['study_evidence_sentence'] = study.apply(lambda r: f"스터디카페 가중집계 {r.study_cafe_weighted_count:.2f}, 공개 학습시설 가중집계 {r.public_weighted_count:.2f}; OSM 잠정400m 외부25%, S4·S3b 제외. " + ('탐색 v0 비교 대상.' if r.study_recommendation_eligible else '관광특구 또는 포함 시설 신호 부족으로 순위 제외.') + f" 진입 가정 후보쌍 {int(r.assumed_connector_count)}, 연결 미해결 {int(r.unknown_connection_count)}; 실제 출입구·현재 운영 미검증.", axis=1)
    save(study, 'study_explanation_scorecard_786.csv')
    cohorts = {
        'cafe_complete': (rank(cafe.loc[cafe.cafe_complete_rank_eligible], 'full_score'), 'full_score', '카페 완전관측 잔차 보정 초안'),
        'cafe_supply_only': (rank(cafe.loc[cafe.cafe_supply_rank_eligible], 'supply_only_score'), 'supply_only_score', '카페 공급 전용 탐색 — 0점포 상권 제외'),
        'study_v0': (rank(study.loc[study.study_recommendation_eligible], 'study_v0_score'), 'study_v0_score', '공부 시설 접근성 탐색 v0 — S4 제외'),
    }
    for key, purposes in [('cafe_study_inside_supply', ['cafe', 'study']), ('meal_cafe_study_inside_supply', ['meal', 'cafe', 'study'])]:
        columns = [p + '_inside_supply_score' for p in purposes]
        eligible = common.recommendation_eligible & common[columns].notna().all(axis=1)
        if 'meal' in purposes:
            eligible &= common.food_eligible
        subset = common.loc[eligible].copy()
        for purpose in purposes:
            subset[purpose + '_percentile_common'] = subset[purpose + '_inside_supply_score'].rank(method='average', pct=True) * 100
        percentile_cols = [p + '_percentile_common' for p in purposes]
        subset['inside_supply_combination_score'] = subset[percentile_cols].mean(axis=1)
        subset['combo_evidence_sentence'] = subset.apply(lambda r: '동일 공식 상권 내부 공급 비교: ' + ', '.join(f'{p} 백분위 {r[p+"_percentile_common"]:.1f}' for p in purposes) + f'; 동일 {len(subset)}개 집단에서 동등 평균. 소비·외부 보행을 포함한 최종 조합 아님.', axis=1)
        cohorts[key] = (rank(subset, 'inside_supply_combination_score'), 'inside_supply_combination_score', ' + '.join(purposes) + ' 내부 공급 비교')

    population_rows, map_checks = [], []
    for key, (ranked, score, title) in cohorts.items():
        ranked['ranking_status'] = key + '_exploratory_not_personal_satisfaction'
        save(ranked, key + '_ranking.csv')
        save(ranked.head(10), key + '_top10.csv')
        save(ranked.head(20), key + '_top20.csv')
        population_rows.append({'purpose_view': key, 'ranking_population': len(ranked), 'top10_rows': min(10, len(ranked)), 'top20_rows': min(20, len(ranked)), 'score_column': score, 'status': ranked.ranking_status.iloc[0]})
        lookup = ranked.set_index('area_code')
        mapped = copy.deepcopy(layer)
        for feature in mapped['features']:
            code = str(feature['properties']['area_code'])
            available = code in lookup.index
            feature['properties'].update({'purpose_view': key, 'score': float(lookup.loc[code, score]) if available else None, 'rank_within_view': int(lookup.loc[code, 'rank']) if available else None, 'is_top10': bool(available and lookup.loc[code, 'rank'] <= 10), 'is_top20': bool(available and lookup.loc[code, 'rank'] <= 20), 'ranking_universe_count': len(ranked), 'map_status': key + '_exploratory_only', 'actual_entrance_verified': False, 'reference_date': '2026-10-06'})
        (OUT / (key + '_map_786.geojson')).write_text(json.dumps(mapped, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        (OUT / (key + '_top20_map.svg')).write_text(svg_map(mapped, ranked, title, len(ranked)), encoding='utf-8')
        map_checks.append((key + '_map_top20_exact', sum(f['properties']['is_top20'] for f in mapped['features']) == 20 and sum(f['properties']['is_top10'] for f in mapped['features']) == 10))

    save(pd.DataFrame(population_rows), 'ranking_population_summary.csv')
    old_supply = pd.read_csv(SOURCE / 'cafe_supply_only_top10.csv', dtype={'area_code': str})
    current_supply = cohorts['cafe_supply_only'][0].head(10)
    comparison = old_supply[['rank', 'area_code', 'area_name']].rename(columns={'rank': 'old_rank'}).merge(current_supply[['rank', 'area_code']].rename(columns={'rank': 'corrected_rank'}), on='area_code', how='outer')
    comparison['change'] = np.select([comparison.old_rank.isna(), comparison.corrected_rank.isna()], ['entered_top10', 'removed_from_top10'], default='retained')
    save(comparison, 'cafe_supply_top10_before_after_correction.csv')

    checks = [
        ('source_codes_786_same', len(cafe) == len(study) == len(common) == 786),
        ('geometry_valid_786', len(layer['features']) == 786 and all(shape(f['geometry']).is_valid for f in layer['features'])),
        ('four_display_repairs_no_material_area_change', len(geometry_audit) == 4 and geometry_audit.area_change_m2.abs().lt(.001).all()),
        ('zero_supply_excluded_48', len(excluded) == 48 and not cafe.loc[(cafe.coffee_stores+cafe.bakery_stores).eq(0), 'cafe_supply_rank_eligible'].any()),
        ('supply_population_corrected_184', len(cohorts['cafe_supply_only'][0]) == 184),
        ('complete_population_218', len(cohorts['cafe_complete'][0]) == 218),
        ('study_population_690', len(cohorts['study_v0'][0]) == 690),
        ('observation_counts_preserved', cafe.score_status.value_counts().to_dict() == {'insufficient': 330, 'supply_only': 232, 'complete': 224}),
        ('insufficient_not_in_cafe_rank', not cafe.loc[cafe.score_status.eq('insufficient'), ['cafe_supply_rank_eligible', 'cafe_complete_rank_eligible']].any().any()),
        ('s4_s3b_excluded', not study.S4_included.any() and study.S3b_role.eq('validation_only_not_scored').all()),
        ('no_actual_entrance_claim', not study.actual_entrance_verified.any()),
        ('missing_cafe_scores_not_filled', cafe.loc[~cafe.cafe_supply_rank_eligible, 'supply_only_score'].isna().all()),
        ('zero_subtype_masked', cafe.loc[cafe.coffee_stores.eq(0), 'C1_subtype_score'].isna().all() and cafe.loc[cafe.bakery_stores.eq(0), 'C2_subtype_score'].isna().all()),
        ('cafe_model_components_equal_parent', all(np.allclose(f.C1_model_contribution + f.C2_model_contribution, f[score]) for key, (f, score, _) in cohorts.items() if key.startswith('cafe_') and key in ['cafe_complete', 'cafe_supply_only'])),
        ('score_ranges', all(f[col].dropna().between(0, 100).all() for f, col, _ in cohorts.values())),
        ('ranks_unique_contiguous', all(f['rank'].tolist() == list(range(1, len(f)+1)) and f.area_code.is_unique for f, _, _ in cohorts.values())),
        ('no_tourism_ranked', all(f.recommendation_eligible.all() for f, _, _ in cohorts.values())),
        ('combo_population_258_each', len(cohorts['cafe_study_inside_supply'][0]) == len(cohorts['meal_cafe_study_inside_supply'][0]) == 258),
        ('combo_inside_only', all(cohorts[k][0].common_distance_basis.eq('same_official_polygon_inside_only_zero_m_no_external_facilities').all() for k in ['cafe_study_inside_supply', 'meal_cafe_study_inside_supply'])),
        ('explanation_786_nonempty', cafe.cafe_evidence_sentence.str.len().gt(0).all() and study.study_evidence_sentence.str.len().gt(0).all()),
    ] + map_checks
    qa = pd.DataFrame([{'check': name, 'status': 'PASS' if bool(ok) else 'FAIL'} for name, ok in checks])
    save(qa, 'steps6_7_qa.csv')
    assert qa.status.eq('PASS').all(), qa.to_string(index=False)
    limitations = pd.DataFrame([
        {'item': 'actual_common_network_final_combination', 'status': 'BLOCKED_INPUT', 'reason': 'meal_point_source_and_shared_route_cache_not_committed'},
        {'item': 'C_stay_study_allowed_evidence', 'status': 'NOT_INCLUDED_IN_V0', 'reason': '427_unknown_S4_excluded_by_team_decision'},
        {'item': 'cafe_study_three_verified_activity_subtypes', 'status': 'NOT_AVAILABLE', 'reason': 'only_two_available_signals_no_invented_third_subtype'},
        {'item': 'Git_remote_push', 'status': 'OUT_OF_CURRENT_SCOPE', 'reason': 'user_requires_local_commit_only'},
    ])
    save(limitations, 'remaining_inputs_and_scope.csv')
    result = {'version': 'steps6_7_20261006', 'qa_pass': len(qa), 'populations': {k: len(v[0]) for k, v in cohorts.items()}, 'zero_supply_cafe_removed_from_rank': len(excluded), 'supply_top10_overlap_count': len(set(old_supply.area_code) & set(current_supply.area_code)), 'display_only_geometry_repairs': len(geometry_audit), 'map_count': len(cohorts), 'map_rows_each': 786, 'cafe_explanation_rows': 786, 'study_explanation_rows': 786, 'score_definition_changed': False, 'ranking_guard_corrected': True, 'inputs': [{'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [cafe_path, study_path, common_path, subtype_path, geo_path, SOURCE / 'cafe_supply_only_top10.csv']]}
    (OUT / 'steps6_7_summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'inputs'}, ensure_ascii=False))


if __name__ == '__main__':
    build()
