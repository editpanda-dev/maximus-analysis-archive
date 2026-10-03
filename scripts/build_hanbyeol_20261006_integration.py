"""Integrate dated OSM route proxies, team meal signal, and cafe/study states.

Final study and three-purpose rankings remain unavailable while S4 evidence
and entrance routing coverage are incomplete. Exploratory scores are labelled.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd


ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/processed/cafe_study_taxonomy/oct06_integration"
BASE=ROOT/"data/processed/cafe_study_taxonomy/oct06_steps_4_7"
WALK=ROOT/"data/processed/cafe_study_taxonomy/osm_walk_20261002"
SNAP=ROOT/"data/external/team_branch_snapshots"


def positive_pct(values:pd.Series)->pd.Series:
    numbers=pd.to_numeric(values,errors="coerce").fillna(0).clip(lower=0)
    positives=numbers.gt(0)
    result=pd.Series(0.,index=values.index)
    if positives.any():result.loc[positives]=numbers.loc[positives].rank(method="average",pct=True)*100
    return result


def top_codes(frame:pd.DataFrame,column:str)->list[str]:
    return frame.sort_values([column,"area_code"],ascending=[False,True]).head(10).area_code.tolist()


def counts_by_area(routes:pd.DataFrame,ids:set[str],radius:int,weight:float,method:str,areas:list[str])->pd.Series:
    col=("walk_access_" if method=="certified" else "proxy_walk_access_")+str(radius)
    valid=routes.loc[routes.place_id.isin(ids)&routes[col].eq(True)]
    inside=valid.loc[valid.route_status.eq("inside_area")].groupby("area_code").place_id.nunique()
    outside=valid.loc[~valid.route_status.eq("inside_area")].groupby("area_code").place_id.nunique()
    return pd.Series({code:inside.get(code,0)+weight*outside.get(code,0) for code in areas})


def build()->None:
    OUT.mkdir(parents=True,exist_ok=True)
    base=pd.read_csv(BASE/"cafe_study_v1_handoff_786.csv",dtype={"area_code":str})
    raw=pd.read_csv(ROOT/"data/processed/cafe_study_taxonomy/cafe_study_score_draft_786.csv",dtype={"area_code":str})
    meal=pd.read_csv(SNAP/"food_shopping_size_neutral_786_d0b6734.csv",dtype={"area_code":str})
    routes=pd.read_csv(WALK/"walk_network_area_poi_access.csv",dtype={"area_code":str,"place_id":str})
    public=pd.read_csv(ROOT/"data/external/study_public_facility_poi.csv",dtype={"place_id":str})
    kakao=pd.read_csv(ROOT/"data/external/kakao_study_stay_pois_20260918.csv",dtype={"place_id":str})
    kakao_routes=pd.read_csv(SNAP/"kakao_walk_c_stay_340_f2846ce.csv",
                             dtype={"place_id":str,"nearest_area_code":str})
    assert len(base)==len(meal)==len(raw)==786
    assert base.area_code.is_unique and set(base.area_code)==set(meal.area_code)==set(raw.area_code)
    assert not routes.duplicated(["area_code","place_id"]).any()
    areas=base.area_code.tolist()
    frame=base.merge(raw[["area_code","access_percentile"]],on="area_code",validate="one_to_one")
    frame=frame.merge(meal[["area_code","food_meal_score_v1","food_meal_supply_v1",
                            "food_meal_sales_coverage","food_meal_sales_signal_missing",
                            "historical_2025_use_allowed"]],on="area_code",validate="one_to_one")
    frame["meal_signal_status"]=np.select([frame.food_meal_sales_coverage.ge(.7),
                                             frame.food_meal_sales_signal_missing.eq(True)],
                                            ["coverage_70pct_plus","missing_sales_signal"],default="partial_sales_coverage")
    frame["meal_source_branch"]="codex/gunwoo/food-shopping-subtypes@d0b6734"
    public_access=public.public_access_verified.eq(1)&public.study_access_verified.eq(1)&public.facility_type.isin(
        ["public_library","reading_room","youth_space"])
    public_mixed=set("public:"+public.loc[public_access&public.operation_status.ne("listed_stale_unverified"),"place_id"])
    public_active=set("public:"+public.loc[public_access&public.operation_status.eq("active_page_with_hours"),"place_id"])
    study=set("kakao:"+kakao.loc[kakao.place_type.eq("study_cafe"),"place_id"])
    assert len(public_mixed)==195 and len(public_active)==16 and len(study)==852
    variants=[]
    for method in ("certified","proxy"):
        for radius in (400,500,600):
            for weight in (0,.25,.5):
                s3a=counts_by_area(routes,study,radius,weight,method,areas)
                pub=counts_by_area(routes,public_mixed,radius,weight,method,areas)
                active=counts_by_area(routes,public_active,radius,weight,method,areas)
                prefix=f"{method}_{radius}_{int(weight*100)}"
                partial=.45*positive_pct(s3a)+.20*positive_pct(pub)+.10*frame.set_index("area_code").access_percentile
                variant=pd.DataFrame({"area_code":areas,"method":method,"radius_m":radius,
                    "nearby_weight":weight,"s3a_study_cafe_count_weighted":s3a.values,
                    "public_access_study_195_count_weighted":pub.values,
                    "public_active_16_count_weighted":active.values,
                    "study_partial_75pct_excluding_S4":partial.reindex(areas).values,
                    "variant_id":prefix,"score_status":"exploratory_75pct_components_only_no_S4"})
                variants.append(variant)
    full=pd.concat(variants,ignore_index=True)
    full.to_csv(OUT/"study_walk_radius_weight_variants_786x18.csv",index=False,encoding="utf-8-sig")
    primary=full.loc[full.variant_id.eq("proxy_400_25")].set_index("area_code")
    certified=full.loc[full.variant_id.eq("certified_400_25")].set_index("area_code")
    frame["study_s3a_walk400_proxy_weighted"]=frame.area_code.map(primary.s3a_study_cafe_count_weighted)
    frame["study_public_walk400_proxy_weighted"]=frame.area_code.map(primary.public_access_study_195_count_weighted)
    frame["study_public_active_page_walk400_proxy_weighted"]=frame.area_code.map(primary.public_active_16_count_weighted)
    frame["study_partial_75pct_proxy"]=frame.area_code.map(primary.study_partial_75pct_excluding_S4)
    frame["study_partial_75pct_certified_lower_bound"]=frame.area_code.map(certified.study_partial_75pct_excluding_S4)
    frame["study_S4_missing_arithmetic_min_given_proxy"]=frame.study_partial_75pct_proxy
    frame["study_S4_missing_arithmetic_max_given_proxy"]=frame.study_partial_75pct_proxy+25
    frame["study_v1_final_score"]=np.nan
    frame["study_v1_status"]="incomplete_S4_and_entrance_evidence"
    frame["cafe_study_final_score"]=np.nan
    frame["meal_cafe_study_final_score"]=np.nan
    frame["network_provenance"]="Geofabrik OSM south-korea-261002; 30m straight entrance connector provisional"

    # Compare the other branch's *nearest area only* Kakao result without
    # treating its 340 routes as full area-by-facility coverage.
    kakao_routes["prefixed_id"]=np.where(kakao_routes.source_dataset.str.startswith("kakao_"),
                                          "kakao:","public:")+kakao_routes.place_id
    compared=kakao_routes.merge(routes,left_on=["nearest_area_code","prefixed_id"],
                                right_on=["area_code","place_id"],how="left",suffixes=("_kakao","_osm"))
    compared["absolute_distance_gap_m"]=(compared.walk_distance_m_kakao-compared.walk_distance_m_osm).abs()
    compared[["prefixed_id","nearest_area_code","route_status_kakao","walk_distance_m_kakao",
              "route_status_osm","walk_distance_m_osm","snap_gap_m","absolute_distance_gap_m"]].to_csv(
                  OUT/"kakao_vs_osm_nearest_area_340.csv",index=False,encoding="utf-8-sig")
    review=pd.read_csv(ROOT/"data/processed/cafe_study_taxonomy/steps_1_3/c_stay_s4_review_queue_v1.csv",
                       dtype={"place_id":str})
    review["candidate_key"]=np.where(review.source_dataset.str.startswith("kakao_"),"kakao:","public:")+review.place_id
    route_focus=compared[["prefixed_id","nearest_area_code","route_status_kakao",
                          "walk_distance_m_kakao","walk_access_400_kakao","walk_access_500_kakao",
                          "walk_access_600_kakao"]].rename(columns={"prefixed_id":"candidate_key",
                              "walk_access_400_kakao":"walk_access_400",
                              "walk_access_500_kakao":"walk_access_500",
                              "walk_access_600_kakao":"walk_access_600"})
    review=review.merge(route_focus,on="candidate_key",how="left",validate="one_to_one")
    review["study_score_eligible"]=False
    review["review_priority"]=np.where(review.walk_access_400.eq(True),"walk400_candidate_check_evidence",
                                       "outside_400_or_route_unavailable")
    assert len(review)==427 and review.decision.eq("unknown").all()
    review.to_csv(OUT/"c_stay_s4_review_priority_427.csv",index=False,encoding="utf-8-sig")

    complete=frame.recommendation_eligible&frame.score_status.eq("complete")&frame.meal_signal_status.eq("coverage_70pct_plus")
    comparison=frame.loc[complete].copy()
    for col in ["cafe_full_score","food_meal_score_v1","study_partial_75pct_proxy"]:
        comparison[col+"_percentile_common"]=comparison[col].rank(method="average",pct=True)*100
    comparison["meal_cafe_study_exploratory_score"]=(comparison.cafe_full_score_percentile_common+
        comparison.food_meal_score_v1_percentile_common+comparison.study_partial_75pct_proxy_percentile_common)/3
    ranked=comparison.sort_values(["meal_cafe_study_exploratory_score","area_code"],ascending=[False,True]).head(20).copy()
    ranked.insert(0,"rank",range(1,len(ranked)+1))
    ranked["status"]="exploratory_partial_study_entrance_proxy_not_final"
    ranked[["rank","area_code","area_name","meal_cafe_study_exploratory_score",
            "cafe_full_score_percentile_common","food_meal_score_v1_percentile_common",
            "study_partial_75pct_proxy_percentile_common","status"]].to_csv(
               OUT/"meal_cafe_study_top20_exploratory.csv",index=False,encoding="utf-8-sig")
    ranked.head(10).to_csv(OUT/"meal_cafe_study_top10_exploratory.csv",index=False,encoding="utf-8-sig")

    summaries=[]
    for method in ("certified","proxy"):
        sample=full.loc[full.method.eq(method)]
        base400=sample.loc[(sample.radius_m.eq(400))&(sample.nearby_weight.eq(.25))]
        base_top=set(top_codes(base400,"study_partial_75pct_excluding_S4"))
        for (radius,weight),part in sample.groupby(["radius_m","nearby_weight"]):
            summaries.append({"method":method,"radius_m":radius,"nearby_weight":weight,
                              "top10_overlap_vs_400m_25pct":len(base_top&set(top_codes(part,"study_partial_75pct_excluding_S4")))/10,
                              "status":"exploratory_S4_and_entrances_unverified"})
    pd.DataFrame(summaries).to_csv(OUT/"study_walk_radius_weight_top10_sensitivity.csv",index=False,encoding="utf-8-sig")
    frame.sort_values("area_code").to_csv(OUT/"cafe_study_meal_integrated_786.csv",index=False,encoding="utf-8-sig")

    layer=json.loads((BASE/"cafe_study_preview_map_786.geojson").read_text(encoding="utf-8"))
    rankmap=dict(zip(ranked.area_code,ranked["rank"]))
    for feature in layer["features"]:
        code=str(feature["properties"]["area_code"])
        feature["properties"]["meal_cafe_study_exploratory_rank"]=rankmap.get(code)
        feature["properties"]["map_status"]="exploratory_partial_study_OSM_entrance_proxy"
    (OUT/"meal_cafe_study_exploratory_map_786.geojson").write_text(json.dumps(layer,ensure_ascii=False),encoding="utf-8")

    qa=pd.DataFrame([
      ("area_codes_unique",len(frame)==frame.area_code.nunique()==786,"786"),
      ("variants_18_each_786",len(full)==18*786,"14148"),
      ("route_area_poi_unique",not routes.duplicated(["area_code","place_id"]).any(),"unique"),
      ("radius_nesting_certified",((routes.walk_access_400.eq(True)&~routes.walk_access_500.eq(True)).sum()==0 and
                                    (routes.walk_access_500.eq(True)&~routes.walk_access_600.eq(True)).sum()==0),"400<=500<=600"),
      ("route_length_at_least_euclidean",(routes.loc[routes.walk_distance_m.notna(),"walk_distance_m"]+1e-6>=
                                            routes.loc[routes.walk_distance_m.notna(),"euclidean_legacy_distance_m"]).all(),"walk>=straight"),
      ("assumed_connector_not_certified",routes.loc[routes.route_status.eq("assumed_straight_entrance_connector"),
                    ["walk_access_400","walk_access_500","walk_access_600"]].isna().all().all(),"all assumed routes unknown in certified flags"),
      ("kakao_nearest_340",len(compared)==340 and compared.prefixed_id.is_unique,"340 nearest-area routes"),
      ("meal_score_786",frame.food_meal_score_v1.notna().all(),"786 exploratory meal scores"),
      ("s4_final_null",frame.study_v1_final_score.isna().all(),"all 786 NA"),
      ("three_purpose_final_null",frame.meal_cafe_study_final_score.isna().all(),"all 786 NA"),
      ("exploratory_top20_common_observed",len(ranked)==20 and ranked.area_code.is_unique,"20"),
      ("map_786",len(layer["features"])==786,"786"),
      ("review_427_unknown",len(review)==427 and review.decision.eq("unknown").all(),"427 unknown"),
    ],columns=["check","passed","expected"])
    qa["status"]=np.where(qa.passed,"PASS","FAIL")
    if not qa.passed.all():raise AssertionError(qa.to_string(index=False))
    qa=pd.concat([qa,pd.DataFrame([
        {"check":"facility_entrance_connector_coverage","passed":False,"expected":"verified entrance links for 7165 proxy and 2046 unresolved pairs","status":"BLOCKED_ROUTE"},
        {"check":"S4_verified_cafe_evidence","passed":False,"expected":"per-place source, quote, reviewer; 427 remain unknown","status":"BLOCKED_EVIDENCE"},
        {"check":"final_study_and_three_purpose_top10","passed":False,"expected":"verified S4 and complete walking coverage","status":"BLOCKED_FINAL_SCORE"},
    ])],ignore_index=True)
    qa.to_csv(OUT/"integration_qa.csv",index=False,encoding="utf-8-sig")
    print({"routes":len(routes),"route_status":routes.route_status.value_counts().to_dict(),
           "kakao_compared_rows":len(compared),"triple_exploratory_universe":len(comparison),
           "qa":qa.status.value_counts().to_dict()})


if __name__=="__main__":build()
