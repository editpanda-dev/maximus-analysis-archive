#!/usr/bin/env python3
"""Collect a current, reviewable Kakao Local snapshot for nightlife POIs.

Only two explicit keyword classes are collected.  The result is a POI source
table, not evidence that every returned venue is suitable for recommendation.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd

try:
    from scripts.collect_kakao_study_pois import build_tiles
except ModuleNotFoundError:
    from collect_kakao_study_pois import build_tiles


KAKAO_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
QUERY_CLASSES = {"night_food": "요리주점", "adult_nightlife": "유흥주점"}


def load_api_key(env_path: Path) -> str:
    key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    if key:
        return key
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("KAKAO_REST_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("KAKAO_REST_API_KEY is not configured")


def fetch_tile(client: httpx.Client, api_key: str, venue_class: str, rect: tuple[float, float, float, float], sleep_seconds: float) -> tuple[list[dict], dict]:
    items: list[dict] = []
    rect_text = ",".join(f"{value:.7f}" for value in rect)
    final_is_end = True
    for page in range(1, 4):  # Kakao Local returns at most 45 items per keyword search.
        response = client.get(
            KAKAO_URL,
            headers={"Authorization": f"KakaoAK {api_key}"},
            params={"query": QUERY_CLASSES[venue_class], "rect": rect_text, "page": page, "size": 15},
        )
        response.raise_for_status()
        payload = response.json()
        for doc in payload.get("documents", []):
            items.append({
                "place_id": str(doc["id"]), "venue_class": venue_class,
                "query": QUERY_CLASSES[venue_class], "place_name": doc.get("place_name", ""),
                "category_name": doc.get("category_name", ""), "address_name": doc.get("address_name", ""),
                "road_address_name": doc.get("road_address_name", ""),
                "longitude": float(doc["x"]), "latitude": float(doc["y"]),
                "place_url": doc.get("place_url", ""),
            })
        final_is_end = bool(payload.get("meta", {}).get("is_end", True))
        if final_is_end:
            break
        time.sleep(sleep_seconds)
    return items, {"rect": rect_text, "document_count": len(items), "truncated": not final_is_end}


def _split_rect(rect: tuple[float, float, float, float]) -> list[tuple[float, float, float, float]]:
    min_x, min_y, max_x, max_y = rect
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    return [
        (min_x, min_y, mid_x, mid_y), (mid_x, min_y, max_x, mid_y),
        (min_x, mid_y, mid_x, max_y), (mid_x, mid_y, max_x, max_y),
    ]


def collect_rect(client, api_key: str, venue_class: str, rect, sleep_seconds: float, depth: int = 0, max_depth: int = 2):
    items, audit = fetch_tile(client, api_key, venue_class, rect, sleep_seconds)
    audit.update({"venue_class": venue_class, "depth": depth})
    if audit["truncated"] and depth < max_depth:
        child_items, child_audits = [], [audit]
        for child in _split_rect(rect):
            collected, audits = collect_rect(client, api_key, venue_class, child, sleep_seconds, depth + 1, max_depth)
            child_items.extend(collected)
            child_audits.extend(audits)
        return child_items, child_audits
    return items, [audit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--areas", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    parser.add_argument("--env", default="services/recommendation-api/.env")
    parser.add_argument("--output", default=None)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--sleep", type=float, default=0.08)
    parser.add_argument("--max-subdivision-depth", type=int, default=2)
    parser.add_argument("--audit-output", default=None)
    args = parser.parse_args()
    areas = gpd.read_file(args.areas).to_crs("EPSG:4326")
    tiles = build_tiles(tuple(float(value) for value in areas.total_bounds), columns=args.columns, rows=args.rows)
    records, audits = [], []
    with httpx.Client(timeout=30) as client:
        for venue_class in QUERY_CLASSES:
            for index, rect in enumerate(tiles, start=1):
                collected, tile_audits = collect_rect(
                    client, load_api_key(Path(args.env)), venue_class, rect, args.sleep,
                    max_depth=args.max_subdivision_depth,
                )
                records.extend(collected)
                audits.extend(tile_audits)
                print(f"[{venue_class}] tile {index}/{len(tiles)} complete")
    frame = pd.DataFrame(records).drop_duplicates("place_id").sort_values(["venue_class", "place_id"])
    frame["snapshot_date"] = date.today().isoformat()
    frame["source"] = "Kakao Local keyword search"
    output = Path(args.output or f"data/external/kakao_nightlife_pois_{date.today():%Y%m%d}.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    audit_output = Path(args.audit_output or output.with_name(f"{output.stem}_collection_audit.json"))
    unresolved = [row for row in audits if row["truncated"] and row["depth"] == args.max_subdivision_depth]
    audit_output.write_text(json.dumps({
        "query_classes": QUERY_CLASSES,
        "base_tile_count": len(tiles),
        "max_subdivision_depth": args.max_subdivision_depth,
        "tile_requests": len(audits),
        "unresolved_truncated_tile_count": len(unresolved),
        "unresolved_truncated_tiles": unresolved,
        "unique_poi_count": int(len(frame)),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(frame):,} unique POIs to {output}")


if __name__ == "__main__":
    main()
