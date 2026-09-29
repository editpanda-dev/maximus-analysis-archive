"""Small geometry checks for the proposed walking-network calculation."""

import unittest

import networkx as nx
from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

from scripts.build_hanbyeol_walk_access import boundary_sources, distance_from_boundary


class WalkBoundaryTests(unittest.TestCase):
    def test_shortest_path_starts_on_boundary_not_centroid(self):
        line = LineString([(0, 0), (1000, 0)])
        graph = nx.Graph()
        graph.add_edge("u", "v", weight=1000)
        seeds, crossing = boundary_sources(box(200, -5, 300, 5), [line], [("u", "v")], STRtree([line]))
        distance, status = distance_from_boundary(
            graph, [line], [("u", "v")], seeds, crossing, (Point(500, 0), 0, 500, 0))
        self.assertEqual(status, "routed")
        self.assertEqual(distance, 200)
        self.assertNotIn("__virtual_area_boundary__", graph)

    def test_no_crossing_is_not_faked_as_euclidean_distance(self):
        line = LineString([(0, 0), (1000, 0)])
        seeds, crossing = boundary_sources(box(200, 20, 300, 30), [line], [("u", "v")], STRtree([line]))
        graph = nx.Graph()
        graph.add_edge("u", "v", weight=1000)
        distance, status = distance_from_boundary(
            graph, [line], [("u", "v")], seeds, crossing, (Point(500, 0), 0, 500, 0))
        self.assertEqual(status, "no_network_boundary_entry")
        self.assertTrue(distance != distance)  # NaN


if __name__ == "__main__":
    unittest.main()
