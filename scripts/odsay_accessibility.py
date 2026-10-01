#!/usr/bin/env python3
"""Build public-transit isochrones with ODsay and aggregate them by district.

The API key is read only from ODSAY_API_KEY. Raw responses are cached so a run
can be reproduced without spending the API quota again.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


API_URL = "https://api.odsay.com/v1/api/searchPubTransIsochrone"


def install_system_trust_store() -> None:
    """Use the macOS/Windows trust store without disabling TLS verification."""
    try:
        import truststore
    except ImportError:
        return
    truststore.inject_into_ssl()


def read_origins(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"origin_id", "origin_name", "longitude", "latitude"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"origin CSV must contain {sorted(required)}")
    result = []
    for row in rows:
        lon, lat = float(row["longitude"]), float(row["latitude"])
        if not (124 <= lon <= 132 and 33 <= lat <= 39.5):
            raise ValueError(f"origin {row['origin_id']} is outside South Korea")
        result.append({**row, "longitude": lon, "latitude": lat})
    return result


def extract_geojson(payload: dict[str, Any]) -> dict[str, Any]:
    if "error" in payload:
        error = payload["error"]
        if isinstance(error, list):
            error = error[0] if error else {}
        message = error.get("message") or error.get("msg")
        raise RuntimeError(f"ODsay error {error.get('code')}: {message}")
    geojson = payload.get("result", {}).get("geojson")
    if not geojson or not geojson.get("features"):
        raise RuntimeError("ODsay returned no isochrone GeoJSON")
    return geojson


def load_cached_payload(path: Path) -> dict[str, Any] | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "error" not in payload:
        return payload
    quarantine = path.with_suffix(".error.json")
    path.replace(quarantine)
    return None


def fetch_isochrone(
    origin: dict[str, Any], api_key: str, search_time: int, timeout: float
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "apiKey": api_key,
            "x": origin["longitude"],
            "y": origin["latitude"],
            "searchTime": search_time,
            "searchMethod": 4,
            "output": "json",
        }
    )
    request = urllib.request.Request(f"{API_URL}?{query}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"ODsay HTTP {exc.code}: {body}") from exc


def merge_feature_collections(items: Iterable[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    features = []
    for origin, geojson in items:
        for feature in geojson.get("features", []):
            copy = json.loads(json.dumps(feature))
            copy.setdefault("properties", {}).update(
                {
                    "origin_id": origin["origin_id"],
                    "origin_name": origin["origin_name"],
                }
            )
            features.append(copy)
    return {"type": "FeatureCollection", "features": features}


def aggregate_districts(
    isochrones_path: Path, districts_path: Path, output_csv: Path, min_coverage: float
) -> None:
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise RuntimeError(
            "district aggregation requires geopandas and shapely; install requirements-odsay.txt"
        ) from exc

    iso = gpd.read_file(isochrones_path).set_crs(4326, allow_override=True)
    districts = gpd.read_file(districts_path)
    if districts.crs is None:
        raise ValueError("district GeoJSON has no CRS")
    name_column = next(
        (c for c in ("ADM_NM", "adm_nm", "emdnm", "EMD_KOR_NM", "name", "dong_name") if c in districts.columns),
        None,
    )
    code_column = next(
        (c for c in ("ADM_CD", "adm_cd", "emdcd", "EMD_CD", "code", "dong_code") if c in districts.columns),
        None,
    )
    if name_column is None:
        raise ValueError("district file needs a dong-name column")

    metric_crs = 5179
    iso = iso.to_crs(metric_crs)
    districts = districts.to_crs(metric_crs)
    records: list[dict[str, Any]] = []
    origin_count = int(iso["origin_id"].nunique())
    for _, district in districts.iterrows():
        area = district.geometry.area
        reached: list[str] = []
        coverages: list[float] = []
        for origin_id, group in iso.groupby("origin_id"):
            coverage = group.geometry.union_all().intersection(district.geometry).area / area
            if coverage >= min_coverage:
                reached.append(str(origin_id))
                coverages.append(coverage)
        if reached:
            records.append(
                {
                    "dong_code": district.get(code_column, "") if code_column else "",
                    "dong_name": district[name_column],
                    "reachable_origin_count": len(reached),
                    "total_origin_count": origin_count,
                    "reachable_origin_ratio": len(reached) / origin_count,
                    "mean_area_coverage": sum(coverages) / len(coverages),
                    "origin_ids": "|".join(sorted(reached)),
                }
            )
    records.sort(key=lambda row: (-row["reachable_origin_ratio"], -row["mean_area_coverage"]))
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(records[0]) if records else [
            "dong_code", "dong_name", "reachable_origin_count", "total_origin_count",
            "reachable_origin_ratio", "mean_area_coverage", "origin_ids",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origins", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/interim/odsay_30min"))
    parser.add_argument("--minutes", type=int, default=30, choices=range(10, 61))
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--max-new-calls", type=int, default=0, help="0 means no batch limit")
    parser.add_argument("--districts", type=Path)
    parser.add_argument("--min-area-coverage", type=float, default=0.10)
    args = parser.parse_args()

    install_system_trust_store()
    api_key = os.environ.get("ODSAY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ODSAY_API_KEY is missing; never put the key in source files")
    if not 0 <= args.min_area_coverage <= 1:
        raise SystemExit("--min-area-coverage must be between 0 and 1")

    origins = read_origins(args.origins)
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    collected = []
    new_calls = 0
    for index, origin in enumerate(origins):
        cache_path = raw_dir / f"{origin['origin_id']}.json"
        payload = load_cached_payload(cache_path) if cache_path.exists() else None
        if payload is None:
            if args.max_new_calls and new_calls >= args.max_new_calls:
                break
            payload = fetch_isochrone(origin, api_key, args.minutes, args.timeout)
            geojson = extract_geojson(payload)
            cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            new_calls += 1
            print(f"[{len(collected) + 1}/{len(origins)}] cached {origin['origin_id']}")
            if index + 1 < len(origins):
                time.sleep(args.sleep)
        else:
            geojson = extract_geojson(payload)
        collected.append((origin, geojson))

    merged_path = args.output_dir / f"isochrones_{args.minutes}min.geojson"
    merged_path.write_text(
        json.dumps(merge_feature_collections(collected), ensure_ascii=False), encoding="utf-8"
    )
    complete = len(collected) == len(origins)
    if args.districts and complete:
        aggregate_districts(
            merged_path,
            args.districts,
            args.output_dir / f"candidate_dongs_{args.minutes}min.csv",
            args.min_area_coverage,
        )
    print(f"saved {len(collected)}/{len(origins)} isochrones to {merged_path}; new API calls={new_calls}")
    if not complete:
        print("batch incomplete; run the same command again to resume from cache")


if __name__ == "__main__":
    main()
