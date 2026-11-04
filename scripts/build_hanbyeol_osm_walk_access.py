"""Route reachable public/study-cafe POIs from every official area boundary.

The output retains unresolved entrances and disconnected paths as unknown.
An OSM graph is a research proxy for legal, current pedestrian access.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import transform
from shapely.strtree import STRtree

from scripts.build_hanbyeol_walk_access import ROOT, load_areas, load_network, snap_pois, boundary_sources


OUT = ROOT / "data/processed/cafe_study_taxonomy/osm_walk_20261002"


def run(nodes: Path, edges: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    areas = load_areas(ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    graph, lines, edge_endpoints, tree = load_network(nodes, edges)
    public = pd.read_csv(ROOT / "data/external/study_public_facility_poi.csv", dtype={"place_id":str})
    kakao = pd.read_csv(ROOT / "data/external/kakao_study_stay_pois_20260918.csv", dtype={"place_id":str})
    pois = pd.concat([public[["place_id","longitude","latitude"]].assign(source="public"),
                      kakao[["place_id","longitude","latitude"]].assign(source="kakao")], ignore_index=True)
    pois.place_id = pois.source + ":" + pois.place_id
    assert pois.place_id.is_unique
    snaps = snap_pois(pois, lines, edge_endpoints, tree, max_gap=30)
    project = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True).transform
    locations = []
    for row in pois.itertuples():
        try:
            point = transform(project, Point(float(row.longitude),float(row.latitude)))
        except (TypeError,ValueError):
            point = Point()
        locations.append(point)
    point_tree = STRtree(locations)
    rows = []
    area_stats = []
    for number,(code,polygon) in enumerate(areas.items(),1):
        seeds, crossing = boundary_sources(polygon, lines, edge_endpoints, tree)
        dist = {}
        if seeds:
            virtual = "__area_boundary__"
            graph.add_node(virtual)
            for node,cost in seeds.items():graph.add_edge(virtual,node,weight=cost)
            try:dist=nx.single_source_dijkstra_path_length(graph,virtual,cutoff=730,weight="weight")
            finally:graph.remove_node(virtual)
        candidate_indices = point_tree.query(polygon.buffer(610))
        count_unresolved = 0
        count_candidates_600 = 0
        for index in candidate_indices:
            i=int(index)
            poi=pois.iloc[i]
            point=locations[i]
            euclidean=polygon.distance(point)
            if euclidean>600:continue
            count_candidates_600 += 1
            snap, snap_status=snaps[poi.place_id]
            gap=np.nan
            if snap is not None and len(snap)>3:gap=snap[3]
            if polygon.covers(point):
                walk=0.0;status="inside_area"
            elif snap_status!="snapped":
                walk=np.nan;status=snap_status
            elif not seeds:
                walk=np.nan;status="no_network_boundary_entry"
            else:
                _,edge_index,at,gap=snap
                u,v=edge_endpoints[edge_index]
                alternatives=[dist.get(u,np.inf)+at,dist.get(v,np.inf)+lines[edge_index].length-at]
                alternatives.extend(abs(at-entry) for entry in crossing.get(edge_index,[]))
                best=min(alternatives)+gap
                walk=float(best) if np.isfinite(best) and best<=700 else np.nan
                status=("routed" if gap<=2 else "assumed_straight_entrance_connector") if np.isfinite(walk) else "no_route_within_700m"
            certified = status in {"routed","inside_area"}
            if not certified:count_unresolved+=1
            rows.append({"area_code":code,"place_id":poi.place_id,
                         "euclidean_legacy_distance_m":euclidean,"walk_distance_m":walk,
                         "walk_access_400":walk<=400 if certified else pd.NA,
                         "walk_access_500":walk<=500 if certified else pd.NA,
                         "walk_access_600":walk<=600 if certified else pd.NA,
                         "proxy_walk_access_400":walk<=400 if pd.notna(walk) else pd.NA,
                         "proxy_walk_access_500":walk<=500 if pd.notna(walk) else pd.NA,
                         "proxy_walk_access_600":walk<=600 if pd.notna(walk) else pd.NA,
                         "snap_gap_m":gap,"route_status":status,
                         "route_origin":"official_polygon_boundary_network_crossing",
                         "network_source":"Geofabrik OSM south-korea-261002.osm.pbf",
                         "network_snapshot_date":"2026-10-02"})
        area_stats.append({"area_code":code,"candidate_pairs_euclidean_600":count_candidates_600,
                           "unresolved_candidate_pairs":count_unresolved,
                           "has_boundary_entry":bool(seeds)})
        if number%100==0:print("areas routed",number,flush=True)
    detail=pd.DataFrame(rows)
    detail.to_csv(OUT/"walk_network_area_poi_access.csv",index=False,encoding="utf-8-sig")
    coverage=pd.DataFrame(area_stats)
    coverage.to_csv(OUT/"walk_route_area_coverage_786.csv",index=False,encoding="utf-8-sig")
    public_good=set("public:"+public.loc[
        public.public_access_verified.eq(1)&public.study_access_verified.eq(1)&
        public.operation_status.ne("listed_stale_unverified")&
        public.facility_type.isin(["public_library","reading_room","youth_space"]),"place_id"])
    public_active=set("public:"+public.loc[
        public.public_access_verified.eq(1)&public.study_access_verified.eq(1)&
        public.operation_status.eq("active_page_with_hours")&
        public.facility_type.isin(["public_library","reading_room","youth_space"]),"place_id"])
    study_ids=set("kakao:"+kakao.loc[kakao.place_type.eq("study_cafe"),"place_id"])
    legacy=pd.read_csv(ROOT/"data/processed/study_public_facility_features.csv",dtype={"area_code":str}).set_index("area_code")
    summary=[]
    for group,ids in [("public_access_study_195_operation_mixed",public_good),
                      ("public_active_page_with_hours",public_active),
                      ("kakao_study_cafe_candidate",study_ids)]:
        relevant=detail.loc[detail.place_id.isin(ids)]
        for method in ("osm_model_connector_le2m","proxy_connector_le30m"):
            scores={}
            prefix="walk_access_" if method.startswith("osm_model") else "proxy_walk_access_"
            for radius in (400,500,600):
                accepted=relevant.loc[relevant[f"{prefix}{radius}"].eq(True)]
                inside=accepted.loc[accepted.route_status.eq("inside_area")].groupby("area_code").place_id.nunique()
                outside=accepted.loc[~accepted.route_status.eq("inside_area")].groupby("area_code").place_id.nunique()
                scores[radius]=pd.Series({code:inside.get(code,0)+.25*outside.get(code,0) for code in areas})
            baseline=set(scores[400].sort_values(ascending=False,kind="stable").head(10).index)
            for radius,values in scores.items():
                top=set(values.sort_values(ascending=False,kind="stable").head(10).index)
                legacy_values=(legacy.study_public_inside_count+.25*legacy.study_public_nearby_only_count)
                legacy_top=set(legacy_values.sort_values(ascending=False,kind="stable").head(10).index)
                summary.append({"group":group,"method":method,"radius_m":radius,
                                "areas_with_positive_signal":int(values.gt(0).sum()),
                                "top10_overlap_vs_400":len(top&baseline)/10,
                                "top10_overlap_vs_euclidean_legacy_400":len(top&legacy_top)/10 if group.startswith("public_access_study") and radius==400 else np.nan,
                                "unresolved_pairs_group":int((~relevant.route_status.isin(["routed","inside_area"])).sum()),
                                "status":"provisional_missing_entrance_or_network"})
    pd.DataFrame(summary).to_csv(OUT/"walk_radius_sensitivity.csv",index=False,encoding="utf-8-sig")
    print({"graph_nodes":graph.number_of_nodes(),"graph_edges":graph.number_of_edges(),
           "candidate_pairs":len(detail),"model_supported":int(detail.route_status.isin(["routed","inside_area"]).sum()),
           "proxy_connector":int(detail.route_status.eq("assumed_straight_entrance_connector").sum()),
           "strict_public_source_ids":len(public_good),"public_active_ids":len(public_active),
           "study_cafe_source_ids":len(study_ids)})


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--nodes",type=Path,required=True)
    parser.add_argument("--edges",type=Path,required=True)
    args=parser.parse_args()
    run(args.nodes,args.edges)
