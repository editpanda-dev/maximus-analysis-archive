#!/usr/bin/env python3
"""Collect a bounded current Kakao Local snapshot for study cafes and Starbucks."""

from __future__ import annotations

import argparse
import os
import time
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd


KAKAO_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
QUERIES = {"study_cafe": "스터디카페", "starbucks": "스타벅스"}


def build_tiles(bounds: tuple[float, float, float, float], *, columns: int, rows: int) -> list[tuple[float, float, float, float]]:
    """Split a bounding box into stable rectangular search areas."""
    min_x, min_y, max_x, max_y = bounds
    x_step = (max_x - min_x) / columns
    y_step = (max_y - min_y) / rows
    return [
        (
            min_x + column * x_step,
            min_y + row * y_step,
            min_x + (column + 1) * x_step,
            min_y + (row + 1) * y_step,
        )
        for row in range(rows)
        for column in range(columns)
    ]


def load_api_key(env_path: Path) -> str:
    if os.environ.get("KAKAO_REST_API_KEY", "").strip():
        return os.environ["KAKAO_REST_API_KEY"].strip()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("KAKAO_REST_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("KAKAO_REST_API_KEY is not configured")


def fetch_tile(
    client: httpx.Client, *, api_key: str, place_type: str, rect: tuple[float, float, float, float], sleep_seconds: float
) -> list[dict]:
    """Fetch all pages for one keyword and tile, retaining provider IDs for deduplication."""
    items = []
    rect_text = ",".join(f"{value:.7f}" for value in rect)
    for page in range(1, 46):
        response = client.get(
            KAKAO_URL,
            headers={"Authorization": f"KakaoAK {api_key}"},
            params={"query": QUERIES[place_type], "rect": rect_text, "page": page, "size": 15},
        )
        response.raise_for_status()
        payload = response.json()
        for document in payload.get("documents", []):
            items.append({
                "place_id": str(document["id"]),
                "place_type": place_type,
                "place_name": document.get("place_name", ""),
                "category_name": document.get("category_name", ""),
                "address_name": document.get("address_name", ""),
                "road_address_name": document.get("road_address_name", ""),
                "longitude": float(document["x"]),
                "latitude": float(document["y"]),
            })
        if payload.get("meta", {}).get("is_end", True):
            break
        time.sleep(sleep_seconds)
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--areas",
        default="data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson",
    )
    parser.add_argument("--env", default="services/recommendation-api/.env")
    parser.add_argument("--output", default=None)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()

    areas = gpd.read_file(args.areas).to_crs("EPSG:4326")
    bounds = tuple(float(value) for value in areas.total_bounds)
    tiles = build_tiles(bounds, columns=args.columns, rows=args.rows)
    api_key = load_api_key(Path(args.env))
    records = []
    with httpx.Client(timeout=30) as client:
        for place_type in QUERIES:
            for index, rect in enumerate(tiles, start=1):
                records.extend(fetch_tile(client, api_key=api_key, place_type=place_type, rect=rect, sleep_seconds=args.sleep))
                print(f"[{place_type}] tile {index}/{len(tiles)} complete")

    output = Path(args.output or f"data/external/kakao_study_stay_pois_{date.today():%Y%m%d}.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(records).drop_duplicates("place_id").sort_values(["place_type", "place_id"])
    frame["snapshot_date"] = date.today().isoformat()
    frame["source"] = "Kakao Local keyword search"
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"wrote {len(frame):,} unique POIs to {output}")


if __name__ == "__main__":
    main()
