#!/usr/bin/env python3
"""Collect a current, reviewable Kakao Local snapshot for nightlife POIs.

Only two explicit keyword classes are collected.  The result is a POI source
table, not evidence that every returned venue is suitable for recommendation.
"""

from __future__ import annotations

import argparse
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


def fetch_tile(client: httpx.Client, api_key: str, venue_class: str, rect: tuple[float, float, float, float], sleep_seconds: float) -> list[dict]:
    items: list[dict] = []
    rect_text = ",".join(f"{value:.7f}" for value in rect)
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
        if payload.get("meta", {}).get("is_end", True):
            break
        time.sleep(sleep_seconds)
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--areas", default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson")
    parser.add_argument("--env", default="services/recommendation-api/.env")
    parser.add_argument("--output", default=None)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--sleep", type=float, default=0.08)
    args = parser.parse_args()
    areas = gpd.read_file(args.areas).to_crs("EPSG:4326")
    tiles = build_tiles(tuple(float(value) for value in areas.total_bounds), columns=args.columns, rows=args.rows)
    records = []
    with httpx.Client(timeout=30) as client:
        for venue_class in QUERY_CLASSES:
            for index, rect in enumerate(tiles, start=1):
                records.extend(fetch_tile(client, load_api_key(Path(args.env)), venue_class, rect, args.sleep))
                print(f"[{venue_class}] tile {index}/{len(tiles)} complete")
    frame = pd.DataFrame(records).drop_duplicates("place_id").sort_values(["venue_class", "place_id"])
    frame["snapshot_date"] = date.today().isoformat()
    frame["source"] = "Kakao Local keyword search"
    output = Path(args.output or f"data/external/kakao_nightlife_pois_{date.today():%Y%m%d}.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"wrote {len(frame):,} unique POIs to {output}")


if __name__ == "__main__":
    main()
