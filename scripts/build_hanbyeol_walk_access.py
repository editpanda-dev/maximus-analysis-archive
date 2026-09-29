"""Route from an official area boundary to POIs on a supplied pedestrian network.

Input walking edges must contain real, connected, legal pedestrian paths in
EPSG:5186. No network is bundled. The script refuses to run without inputs.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform
from shapely import wkt
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/cafe_study_taxonomy"


def points_of(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Point":
        return [geometry]
    if geometry.geom_type == "LineString":
        return [Point(geometry.coords[0]), Point(geometry.coords[-1])]
    if hasattr(geometry, "geoms"):
        return [p for part in geometry.geoms for p in points_of(part)]
    return []


def load_areas(path: Path):
    project = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True).transform
    raw = json.loads(path.read_text(encoding="utf-8"))
    areas = {}
    for item in raw["features"]:
        code = str(item["properties"]["area_code"])
        areas[code] = transform(project, shape(item["geometry"]))
    if len(areas) != 786:
        raise ValueError("Expected 786 unique official polygons")
    return areas


def load_network(nodes_file: Path, edges_file: Path):
    nodes = pd.read_csv(nodes_file, dtype={"node_id": str}).set_index("node_id")
    edges = pd.read_csv(edges_file, dtype={"u": str, "v": str})
    if not {"x", "y"}.issubset(nodes.columns) or not {"u", "v", "geometry_wkt"}.issubset(edges.columns):
        raise ValueError("nodes: node_id,x,y; edges: u,v,geometry_wkt are required")
    if "oneway_walk" in edges and edges.oneway_walk.fillna(0).astype(int).ne(0).any():
        raise ValueError("One-way walking edges require directed routing; this version accepts bidirectional edges only")
    if nodes.index.has_duplicates or (nodes[["x", "y"]].isna().any().any()):
        raise ValueError("Network nodes must have unique IDs and projected coordinates")
    graph = nx.Graph()
    lines = []
    edge_rows = []
    for i, row in edges.iterrows():
        if row.u not in nodes.index or row.v not in nodes.index or row.u == row.v:
            raise ValueError(f"Invalid edge endpoints on row {i}")
        line = wkt.loads(row.geometry_wkt)
        if line.geom_type != "LineString" or line.length <= 0:
            raise ValueError(f"Invalid pedestrian geometry on row {i}")
        u = Point(float(nodes.at[row.u, "x"]), float(nodes.at[row.u, "y"]))
        v = Point(float(nodes.at[row.v, "x"]), float(nodes.at[row.v, "y"]))
        if Point(line.coords[0]).distance(u) > 2 or Point(line.coords[-1]).distance(v) > 2:
            raise ValueError(f"Edge geometry endpoints must match u,v within 2m: {i}")
        if "length_m" in edges.columns and pd.notna(row.length_m):
            if abs(float(row.length_m) - line.length) > max(2, line.length * .02):
                raise ValueError(f"Edge length differs from geometry on row {i}")
        # Parallel edges with the same endpoints must be represented by an
        # intermediate node; otherwise boundary entry offsets are ambiguous.
        if graph.has_edge(row.u, row.v):
            raise ValueError(f"Parallel u,v edges require segmentation: {i}")
        graph.add_edge(row.u, row.v, weight=line.length)
        lines.append(line)
        edge_rows.append((row.u, row.v))
    return graph, lines, edge_rows, STRtree(lines)


def snap_pois(pois: pd.DataFrame, lines, edges, tree, max_gap: float = 30):
    project = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True).transform
    result = {}
    for row in pois.itertuples(index=False):
        if pd.isna(row.longitude) or pd.isna(row.latitude):
            result[row.place_id] = (None, "invalid_coordinate")
            continue
        point = transform(project, Point(float(row.longitude), float(row.latitude)))
        near = tree.query(point.buffer(max_gap))
        if len(near) == 0:
            result[row.place_id] = ((point, None, None, None), "no_pedestrian_edge_within_30m")
            continue
        index = min(near, key=lambda i: lines[int(i)].distance(point))
        index = int(index)
        gap = lines[index].distance(point)
        if gap > max_gap:
            result[row.place_id] = ((point, None, None, None), "no_pedestrian_edge_within_30m")
            continue
        result[row.place_id] = ((point, index, lines[index].project(point), gap), "snapped")
    return result


def boundary_sources(polygon, lines, edges, tree):
    seeds = defaultdict(lambda: float("inf"))
    crossing = defaultdict(list)
    for index in tree.query(polygon.boundary):
        index = int(index)
        line = lines[index]
        hits = points_of(line.intersection(polygon.boundary))
        u, v = edges[index]
        for hit in hits:
            at = line.project(hit)
            crossing[index].append(at)
            seeds[u] = min(seeds[u], at)
            seeds[v] = min(seeds[v], line.length - at)
    return seeds, crossing


def distance_from_boundary(graph, lines, edges, seeds, crossing, snap, cutoff=660):
    if not seeds:
        return np.nan, "no_network_boundary_entry"
    supernode = "__virtual_area_boundary__"
    graph.add_node(supernode)
    for node, cost in seeds.items():
        graph.add_edge(supernode, node, weight=cost)
    try:
        distances = nx.single_source_dijkstra_path_length(graph, supernode, cutoff=cutoff, weight="weight")
    finally:
        graph.remove_node(supernode)
    point, index, at, gap = snap
    u, v = edges[index]
    values = [distances.get(u, np.inf) + at, distances.get(v, np.inf) + lines[index].length - at]
    values.extend(abs(at - entry) for entry in crossing.get(index, []))
    best = min(values) + gap
    return (best, "routed") if np.isfinite(best) and best <= 630 else (np.nan, "no_route_within_630m")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", type=Path, required=True, help="node_id,x,y in EPSG:5186")
    parser.add_argument("--edges", type=Path, required=True,
                        help="u,v,geometry_wkt,length_m for legal walking edges in EPSG:5186")
    parser.add_argument("--network-source", required=True)
    parser.add_argument("--network-snapshot-date", required=True)
    parser.add_argument("--areas", type=Path, default=ROOT / "data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    args = parser.parse_args()
    if not args.nodes.exists() or not args.edges.exists():
        parser.error("Real pedestrian network input missing; no synthetic distances are produced")
    areas = load_areas(args.areas)
    graph, lines, edges, tree = load_network(args.nodes, args.edges)
    public = pd.read_csv(ROOT / "data/external/study_public_facility_poi.csv", dtype={"place_id": str})
    kakao = pd.read_csv(ROOT / "data/external/kakao_study_stay_pois_20260918.csv", dtype={"place_id": str})
    pois = pd.concat([
        public[["place_id", "longitude", "latitude"]].assign(source_dataset="public_poi_20260921"),
        kakao[["place_id", "longitude", "latitude"]].assign(source_dataset="kakao_20260918")
    ], ignore_index=True)
    pois["place_id"] = pois.source_dataset + ":" + pois.place_id
    snaps = snap_pois(pois, lines, edges, tree)
    rows = []
    for code, polygon in areas.items():
        seeds, crossing = boundary_sources(polygon, lines, edges, tree)
        for poi in pois.itertuples(index=False):
            snap, status = snaps[poi.place_id]
            if snap is None:
                continue
            euclid = polygon.distance(snap[0])
            if euclid > 630:
                continue  # A legal path cannot be shorter than Euclidean distance.
            if polygon.covers(snap[0]):
                walk, route_status = 0.0, "inside_area"
            elif status != "snapped":
                walk, route_status = np.nan, status
            else:
                walk, route_status = distance_from_boundary(graph, lines, edges, seeds, crossing, snap)
                if route_status == "routed" and snap[3] > 2:
                    route_status = "needs_entrance_connector_validation"
            verified_route = route_status in {"routed", "inside_area"}
            rows.append({"area_code": code, "place_id": poi.place_id,
                         "walk_distance_m": walk,
                         "walk_access_400": bool(walk <= 400) if verified_route else pd.NA,
                         "walk_access_500": bool(walk <= 500) if verified_route else pd.NA,
                         "walk_access_600": bool(walk <= 600) if verified_route else pd.NA,
                         "snap_gap_m": snap[3] if snap else np.nan,
                         "network_source": args.network_source,
                         "network_snapshot_date": args.network_snapshot_date,
                         "route_status": route_status, "euclidean_legacy_distance_m": euclid})
    OUT.mkdir(parents=True, exist_ok=True)
    output = pd.DataFrame(rows)
    output.to_csv(OUT / "walk_network_area_poi_access.csv", index=False, encoding="utf-8-sig")
    if output.empty:
        raise ValueError("No POIs matched the pedestrian network; inspect graph and coordinate reference")
    public_legacy_ids = set("public_poi_20260921:" + public.loc[
        public.public_feature_included.eq(1), "place_id"])
    study_cafe_ids = set("kakao_20260918:" + kakao.loc[kakao.place_type.eq("study_cafe"), "place_id"])
    legacy = pd.read_csv(ROOT / "data/processed/study_public_facility_features.csv", dtype={"area_code": str})
    summaries = []
    for group_name, ids in [("legacy_public_236_for_method_comparison", public_legacy_ids),
                            ("kakao_study_cafe_candidates", study_cafe_ids)]:
        subset = output[output.place_id.isin(ids)]
        scores = {}
        for radius in (400, 500, 600):
            accepted = subset[subset[f"walk_access_{radius}"].eq(True).fillna(False)]
            inside = accepted[accepted.route_status.eq("inside_area")].groupby("area_code").place_id.nunique()
            outside = accepted[~accepted.route_status.eq("inside_area")].groupby("area_code").place_id.nunique()
            scores[radius] = pd.Series({code: inside.get(code, 0) + .25 * outside.get(code, 0)
                                        for code in areas})
        enough = scores[400].gt(0).sum() >= 10
        top400 = set(scores[400][scores[400].gt(0)].sort_values(ascending=False, kind="stable").head(10).index)
        legacy_score = legacy.set_index("area_code").study_public_inside_count + .25 * legacy.set_index(
            "area_code").study_public_nearby_only_count
        for radius, values in scores.items():
            top = set(values[values.gt(0)].sort_values(ascending=False, kind="stable").head(10).index)
            summaries.append({"group": group_name, "radius_m": radius,
                              "eligible_area_count": int(values.gt(0).sum()),
                              "top10_overlap_vs_400": len(top & top400) / 10 if enough and len(top) == 10 else np.nan,
                              "rank_spearman_vs_400": float(spearmanr(scores[400], values).statistic)
                                  if enough else np.nan,
                              "top10_overlap_vs_euclidean_legacy_400": (
                                  len(top & set(legacy_score.sort_values(ascending=False).head(10).index)) / 10
                                  if group_name.startswith("legacy_public") and radius == 400 and enough else np.nan),
                              "network_source": args.network_source,
                              "status": "computed_from_pedestrian_graph" if enough else "insufficient_verified_routes"})
    pd.DataFrame(summaries).to_csv(OUT / "walk_radius_sensitivity.csv", index=False, encoding="utf-8-sig")
    print(f"Wrote {len(output)} area-POI route evaluations")


if __name__ == "__main__":
    main()
