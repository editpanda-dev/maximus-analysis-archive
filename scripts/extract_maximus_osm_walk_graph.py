"""Extract a conservative pedestrian graph from a dated Geofabrik OSM PBF.

The graph is for research, not legal access certification. OSM's missing sidewalk
and entrance tags are recorded as limitations of the resulting distances.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import osmium
from pyproj import Transformer


ALLOW = {"footway", "path", "pedestrian", "steps", "living_street", "residential",
         "service", "tertiary", "unclassified", "track", "secondary", "primary"}
REJECT_ACCESS = {"no", "private", "customers", "permit"}
BOX = (126.89, 37.48, 127.18, 37.72)


class WalkHandler(osmium.SimpleHandler):
    def __init__(self, nodes_writer, edges_writer):
        super().__init__()
        self.nodes_writer = nodes_writer
        self.edges_writer = edges_writer
        self.project = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
        self.seen_nodes = set()
        self.seen_edges = set()
        self.way_count = 0
        self.edge_count = 0

    def way(self, way):
        tag = way.tags.get("highway")
        if tag not in ALLOW or way.tags.get("foot") in REJECT_ACCESS or way.tags.get("access") in REJECT_ACCESS:
            return
        if way.tags.get("motor_vehicle") == "yes" and tag == "track" and way.tags.get("foot") != "yes":
            return
        if way.tags.get("sidewalk") == "no" and tag in {"primary", "secondary"} and way.tags.get("foot") != "yes":
            return
        points = []
        for node in way.nodes:
            if not node.location.valid():
                continue
            x, y = self.project.transform(node.lon, node.lat)
            points.append((str(node.ref), float(node.lon), float(node.lat), x, y))
        if len(points) < 2:
            return
        used = False
        for start, end in zip(points, points[1:]):
            if not any(BOX[0] <= item[1] <= BOX[2] and BOX[1] <= item[2] <= BOX[3]
                       for item in (start, end)):
                continue
            if start[0] == end[0]:
                continue
            length = ((start[3]-end[3])**2+(start[4]-end[4])**2)**.5
            if length < .01:
                continue
            key = tuple(sorted((start[0],end[0])))
            if key in self.seen_edges:
                continue
            self.seen_edges.add(key)
            for item in (start, end):
                if item[0] not in self.seen_nodes:
                    self.nodes_writer.writerow([item[0],item[3],item[4]])
                    self.seen_nodes.add(item[0])
            wkt = f"LINESTRING ({start[3]} {start[4]}, {end[3]} {end[4]})"
            self.edges_writer.writerow([start[0],end[0],wkt,length,0,str(way.id),tag])
            self.edge_count += 1
            used = True
        self.way_count += used


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "nodes.csv").open("w", newline="") as nodefile, (args.out / "edges.csv").open("w", newline="") as edgefile:
        nodes = csv.writer(nodefile)
        edges = csv.writer(edgefile)
        nodes.writerow(["node_id","x","y"])
        edges.writerow(["u","v","geometry_wkt","length_m","oneway_walk","osm_way_id","highway"])
        handler = WalkHandler(nodes, edges)
        handler.apply_file(str(args.pbf), locations=True, idx="flex_mem")
    print({"used_ways":handler.way_count,"edges":handler.edge_count,"nodes":len(handler.seen_nodes),"bbox_wgs84":BOX})


if __name__ == "__main__":
    main()
