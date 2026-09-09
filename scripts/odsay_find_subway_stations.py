#!/usr/bin/env python3
"""Find physical subway stations inside a district with ODsay pointSearch."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from odsay_accessibility import install_system_trust_store


API_URL = "https://api.odsay.com/v1/api/pointSearch"


def polygon_rings(geometry: dict[str, Any]):
    if geometry["type"] == "Polygon":
        yield from geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from polygon
    else:
        raise ValueError(f"unsupported geometry: {geometry['type']}")


def exterior_points(geometry: dict[str, Any]) -> list[list[float]]:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"][0]
    return [point for polygon in geometry["coordinates"] for point in polygon[0]]


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_geometry(x: float, y: float, geometry: dict[str, Any]) -> bool:
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    return any(
        point_in_ring(x, y, polygon[0])
        and not any(point_in_ring(x, y, hole) for hole in polygon[1:])
        for polygon in polygons
    )


def boundary_distance_m(x: float, y: float, geometry: dict[str, Any]) -> float:
    cos_lat = math.cos(math.radians(y))
    best = float("inf")
    for ring in polygon_rings(geometry):
        for first, second in zip(ring, ring[1:]):
            ax, ay = (first[0] - x) * 111_320 * cos_lat, (first[1] - y) * 110_540
            bx, by = (second[0] - x) * 111_320 * cos_lat, (second[1] - y) * 110_540
            dx, dy = bx - ax, by - ay
            denominator = dx * dx + dy * dy
            t = max(0.0, min(1.0, -(ax * dx + ay * dy) / denominator)) if denominator else 0.0
            best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def district_feature(path: Path, code: str) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for feature in data["features"]:
        props = feature.get("properties", {})
        if str(props.get("SIG_CD", props.get("code", ""))) == code:
            return feature
    raise ValueError(f"district code {code} not found")


def search_circle(geometry: dict[str, Any]) -> tuple[float, float, int]:
    points = exterior_points(geometry)
    lon = sum(p[0] for p in points) / len(points)
    lat = sum(p[1] for p in points) / len(points)
    radius = max(haversine_m(lon, lat, p[0], p[1]) for p in points) + 500
    return lon, lat, math.ceil(radius)


def fetch_stations(lon: float, lat: float, radius: int, api_key: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {"apiKey": api_key, "x": lon, "y": lat, "radius": radius, "stationClass": "2", "output": "json"}
    )
    with urllib.request.urlopen(f"{API_URL}?{query}", timeout=30) as response:
        return json.load(response)


def normalized_station_name(name: str) -> str:
    return re.sub(r"\([^)]*\)|역$|\s+", "", name).strip()


def physical_stations(
    payload: dict[str, Any], geometry: dict[str, Any], boundary_tolerance_m: float = 20
) -> list[dict[str, Any]]:
    if "error" in payload:
        error = payload["error"]
        raise RuntimeError(f"ODsay error {error.get('code')}: {error.get('msg')}")
    rows = payload.get("result", {}).get("station", [])
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        if int(row.get("stationClass", 0)) != 2:
            continue
        lon, lat = float(row["x"]), float(row["y"])
        inside = point_in_geometry(lon, lat, geometry)
        boundary_distance = boundary_distance_m(lon, lat, geometry)
        if not inside and boundary_distance > boundary_tolerance_m:
            continue
        name = row.get("stationNameKor") or row["stationName"]
        key = normalized_station_name(name)
        group = groups.setdefault(
            key,
            {
                "origin_id": f"subway_{key}",
                "origin_name": name,
                "longitude": lon,
                "latitude": lat,
                "origin_type": "subway",
                "source": "ODsay pointSearch",
                "district_match": "inside" if inside else "boundary_tolerance",
                "boundary_distance_m": round(boundary_distance, 1),
                "odsay_station_ids": set(),
                "lines": set(),
            },
        )
        group["odsay_station_ids"].add(str(row["stationID"]))
        line = row.get("laneNameKor") or row.get("laneName")
        if line:
            group["lines"].add(str(line))
    result = []
    for group in groups.values():
        group["odsay_station_ids"] = "|".join(sorted(group["odsay_station_ids"]))
        group["lines"] = "|".join(sorted(group["lines"]))
        result.append(group)
    return sorted(result, key=lambda row: row["origin_name"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--districts", type=Path, required=True)
    parser.add_argument("--district-code", default="11230")
    parser.add_argument("--output", type=Path, default=Path("data/external/odsay_subway_stations_dongdaemun.csv"))
    parser.add_argument("--raw-cache", type=Path, default=Path("data/interim/odsay_stations_dongdaemun.json"))
    parser.add_argument("--boundary-tolerance-m", type=float, default=20)
    args = parser.parse_args()
    install_system_trust_store()
    feature = district_feature(args.districts, args.district_code)
    lon, lat, radius = search_circle(feature["geometry"])
    if args.raw_cache.exists():
        payload = json.loads(args.raw_cache.read_text(encoding="utf-8"))
    else:
        api_key = os.environ.get("ODSAY_API_KEY", "").strip()
        if not api_key:
            raise SystemExit("ODSAY_API_KEY is missing and no raw cache exists")
        payload = fetch_stations(lon, lat, radius, api_key)
        args.raw_cache.parent.mkdir(parents=True, exist_ok=True)
        args.raw_cache.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = physical_stations(payload, feature["geometry"], args.boundary_tolerance_m)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "origin_id", "origin_name", "longitude", "latitude", "origin_type", "source",
        "district_match", "boundary_distance_m", "odsay_station_ids", "lines",
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved {len(rows)} physical subway stations to {args.output}")


if __name__ == "__main__":
    main()
