"""Walking distances on the OpenStreetMap pedestrian network, checked against Kakao.

Kakao's walking-route API allows about 1,000 calls a day, so the ~182k
(area, 50m store cell) pairs from `collect_food_shopping_walk_routes.py` are
computed locally on the OSM walk network instead. The Kakao routes already
collected are used only to validate this network distance.

Per area, a virtual source joins every network node inside the polygon at
distance 0 and every node within SOURCE_SNAP_M of the polygon at its straight
distance to the boundary; one bounded Dijkstra then gives the walking distance
from the area boundary to each node. A cell's distance is the distance of its
nearest node plus the straight snap from the cell's store position to that node.

Output uses the Kakao cache schema, so `build_food_shopping_v1.py --walk-routes`
reads it unchanged. Map data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
from collect_food_shopping_walk_routes import cell_id, outside_cells  # noqa: E402
from build_food_shopping_v1 import read_sbiz_seoul  # noqa: E402

CRS = 5181
SOURCE_SNAP_M = 50
CUTOFF_M = 600
BEYOND = 9999.0
VALIDATION_GATE = {"within_400_agreement_min": 0.90, "median_abs_error_max_m": 50.0}


def load_graph(path: Path, areas: gpd.GeoDataFrame) -> nx.MultiDiGraph:
    import osmnx as ox

    # Keep osmnx's Overpass response cache next to the graph, outside the repo.
    ox.settings.cache_folder = str(path.parent / "osmnx_http_cache")
    if path.exists():
        graph = ox.load_graphml(path)
    else:
        hull = areas.to_crs(4326).buffer(0.01).union_all().convex_hull
        graph = ox.graph_from_polygon(hull, network_type="walk", simplify=True, retain_all=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(graph, path)
    return ox.project_graph(graph, to_crs=f"EPSG:{CRS}")


def undirected_lengths(graph: nx.MultiDiGraph) -> nx.Graph:
    simple = nx.Graph()
    for u, v, data in graph.edges(data=True):
        length = float(data.get("length", 0.0))
        if not simple.has_edge(u, v) or simple[u][v]["length"] > length:
            simple.add_edge(u, v, length=length)
    return simple


def area_distances(simple: nx.Graph, node_ids: np.ndarray, node_xy: np.ndarray, tree: cKDTree, polygon) -> dict:
    """Bounded Dijkstra from the polygon boundary to every reachable node."""
    minx, miny, maxx, maxy = polygon.bounds
    near = tree.query_ball_point([(minx + maxx) / 2, (miny + maxy) / 2], r=np.hypot(maxx - minx, maxy - miny) / 2 + SOURCE_SNAP_M)
    pts = gpd.GeoSeries(gpd.points_from_xy(node_xy[near, 0], node_xy[near, 1]), crs=CRS)
    gap = pts.distance(polygon).to_numpy()
    source = "__area__"
    simple.add_node(source)
    for idx, d in zip(near, gap):
        if d <= SOURCE_SNAP_M:
            simple.add_edge(source, node_ids[idx], length=float(d))
    try:
        dist = nx.single_source_dijkstra_path_length(simple, source, cutoff=CUTOFF_M, weight="length")
    finally:
        simple.remove_node(source)
    dist.pop(source, None)
    return dist


def compute(cells: pd.DataFrame, graph: nx.MultiDiGraph, areas: gpd.GeoDataFrame) -> pd.DataFrame:
    simple = undirected_lengths(graph)
    node_ids = np.array(list(simple.nodes))
    node_xy = np.array([(graph.nodes[n]["x"], graph.nodes[n]["y"]) for n in node_ids])
    tree = cKDTree(node_xy)
    cell_xy = cells[["x", "y"]].to_numpy()
    snap, nearest = tree.query(cell_xy)
    cells = cells.assign(snap_m=snap, node=node_ids[nearest])
    geom = areas.set_index("area_code").geometry
    out = []
    for i, (code, group) in enumerate(cells.groupby("area_code")):
        dist = area_distances(simple, node_ids, node_xy, tree, geom[code])
        d = group.node.map(dist).astype(float) + group.snap_m
        out.append(pd.DataFrame({
            "area_code": code, "cell_id": group.cell_id, "euclidean_m": group.euclidean_m,
            "walk_distance_m": d.fillna(BEYOND).round(1),
            "route_status": np.where(d.isna(), "OSM_BEYOND_CUTOFF", "OSM_OK"), "walk_time_s": np.nan,
        }))
        if (i + 1) % 100 == 0:
            print(f"{i + 1} areas", flush=True)
    return pd.concat(out, ignore_index=True)


def validate(osm: pd.DataFrame, kakao: pd.DataFrame, limit: float = 400) -> dict:
    k = kakao[kakao.route_status.isin(["OK", "SAME_POINT"])].astype({"walk_distance_m": float})
    m = k.merge(osm, on=["area_code", "cell_id"], suffixes=("_kakao", "_osm"))
    ok = m[m.route_status_kakao == "OK"]
    err = (ok.walk_distance_m_osm.clip(upper=CUTOFF_M) - ok.walk_distance_m_kakao.clip(upper=CUTOFF_M))
    agree = ((m.walk_distance_m_osm <= limit) == (m.walk_distance_m_kakao <= limit)).mean()
    report = {
        "pairs_compared": int(len(m)),
        "kakao_ok_pairs": int(len(ok)),
        "within_400_agreement": round(float(agree), 4),
        "median_abs_error_m": round(float(err.abs().median()), 1),
        "p90_abs_error_m": round(float(err.abs().quantile(0.9)), 1),
        "mean_signed_error_m": round(float(err.mean()), 1),
        "kakao_euclid_ratio_median": round(float((ok.walk_distance_m_kakao / ok.euclidean_m_kakao.astype(float).clip(lower=1)).median()), 3),
        "gate": VALIDATION_GATE,
    }
    report["passed"] = bool(
        report["within_400_agreement"] >= VALIDATION_GATE["within_400_agreement_min"]
        and report["median_abs_error_m"] <= VALIDATION_GATE["median_abs_error_max_m"]
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sbiz-zip", type=Path, required=True)
    parser.add_argument("--areas", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"))
    parser.add_argument("--graph", type=Path, required=True, help="OSM 보행망 graphml 캐시 (저장소 밖)")
    parser.add_argument("--kakao-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="OSM 보행거리 CSV (저장소 밖)")
    parser.add_argument("--validation", type=Path, default=Path("data/processed/food_shopping_v1/walk_route_validation.json"))
    parser.add_argument("--validate-only", action="store_true", help="카카오 표본이 있는 상권만 계산해 검증")
    args = parser.parse_args()

    areas = gpd.read_file(args.areas).to_crs(CRS)
    areas["area_code"] = areas.area_code.astype(str).str.zfill(7)
    sbiz = read_sbiz_seoul(args.sbiz_zip)
    stores = gpd.GeoDataFrame(geometry=gpd.points_from_xy(sbiz["경도"], sbiz["위도"]), crs=4326).to_crs(CRS)
    stores["cell_id"] = cell_id(stores.geometry.x, stores.geometry.y)
    cells = outside_cells(stores, areas, 400)
    kakao = pd.read_csv(args.kakao_cache, dtype={"area_code": str, "cell_id": str})
    if args.validate_only:
        cells = cells[cells.area_code.isin(set(kakao.area_code))]
    print(f"cells {len(cells):,} in {cells.area_code.nunique()} areas", flush=True)
    graph = load_graph(args.graph, areas)
    osm = compute(cells, graph, areas)
    report = validate(osm, kakao)
    report["osm_cells"] = int(len(osm))
    report["osm_beyond_cutoff_share"] = round(float((osm.route_status == "OSM_BEYOND_CUTOFF").mean()), 4)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    osm.to_csv(args.output, index=False)
    args.validation.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
