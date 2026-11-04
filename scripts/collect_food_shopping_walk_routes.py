"""Collect Kakao walking-route distances for the food/shopping 400m walk area.

Each store that sits outside an official area but within 400m in a straight
line needs a walking distance from that area (all stores, because the
specialisation index uses every store as its denominator). Routing every
store-area pair would take ~800k calls, so stores are grouped into 50m grid
cells and one route is queried per (area, cell): from the nearest point on the
area boundary to the mean position of the cell's stores (~182k calls). A
store's walking distance is its cell's distance, within about +-35m.

The boundary origin is a transparent proxy for an entrance, the same rule as
`scripts/build_kakao_walk_access.py` used for cafes and leisure.

Results are appended to a cache CSV outside the repository (API responses are
not committed) so the run can stop and resume. The key comes from the
KAKAO_REST_API_KEY environment variable and is never printed.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.ops import nearest_points

sys.path.insert(0, str(Path(__file__).parent))
from build_food_shopping_v1 import read_sbiz_seoul  # noqa: E402

KAKAO_WALK_URL = "https://dapi.kakao.com/v2/routing/walk"
CELL_M = 50
CACHE_COLUMNS = ["area_code", "cell_id", "route_status", "walk_distance_m", "walk_time_s", "euclidean_m"]
STOP_STATUSES = {401, 403, 429}


def cell_id(x: pd.Series, y: pd.Series, size: int = CELL_M) -> pd.Series:
    return (x // size).astype(int).astype(str) + "_" + (y // size).astype(int).astype(str)


def outside_cells(stores: gpd.GeoDataFrame, areas: gpd.GeoDataFrame, buffer_m: float) -> pd.DataFrame:
    """(area, cell) pairs for stores outside the polygon but within the straight-line buffer.

    Walking distance is never shorter than the straight line, so the buffer is
    a complete candidate set.
    """
    polygons = areas[["area_code", "geometry"]]
    buffered = polygons.assign(geometry=polygons.buffer(buffer_m))
    inside = gpd.sjoin(stores[["geometry"]], polygons, predicate="intersects")
    near = gpd.sjoin(stores[["cell_id", "geometry"]], buffered, predicate="intersects")
    inside_pairs = pd.MultiIndex.from_arrays([inside.index, inside.area_code])
    near = near[~pd.MultiIndex.from_arrays([near.index, near.area_code]).isin(inside_pairs)]
    near = near.assign(x=near.geometry.x, y=near.geometry.y)
    cells = near.groupby(["area_code", "cell_id"]).agg(x=("x", "mean"), y=("y", "mean"), stores=("x", "size")).reset_index()
    geom = polygons.set_index("area_code").geometry
    points = gpd.GeoSeries(gpd.points_from_xy(cells.x, cells.y), crs=areas.crs)
    origins = [nearest_points(p, geom[a].boundary)[1] for p, a in zip(points, cells.area_code)]
    origins = gpd.GeoSeries(origins, crs=areas.crs)
    cells["euclidean_m"] = points.distance(origins).round(1).to_numpy()
    o, d = origins.to_crs(4326), points.to_crs(4326)
    cells["start_x"], cells["start_y"] = o.x.to_numpy(), o.y.to_numpy()
    cells["end_x"], cells["end_y"] = d.x.to_numpy(), d.y.to_numpy()
    return cells


def fetch_walk_route(session: requests.Session, api_key: str, row, timeout: int = 30) -> dict:
    response = session.get(
        KAKAO_WALK_URL,
        headers={"Authorization": f"KakaoAK {api_key}"},
        params={"start_x": row.start_x, "start_y": row.start_y, "end_x": row.end_x, "end_y": row.end_y, "route_mode": "SHORTEST"},
        timeout=timeout,
    )
    if response.status_code in STOP_STATUSES or "limit" in response.text.lower():
        # Kakao reports the daily quota as HTTP 400 "API limit has been exceeded."
        raise PermissionError(f"HTTP {response.status_code} quota or permission")
    response.raise_for_status()
    payload = response.json()
    status = str(payload.get("status", "UNKNOWN_RESPONSE"))
    if status == "SAME_POINT":
        return {"route_status": status, "walk_distance_m": 0.0, "walk_time_s": 0.0}
    props = payload.get("route", {}).get("properties", {})
    if status != "OK" or "totalDistance" not in props:
        return {"route_status": status if status != "OK" else "MALFORMED_OK_RESPONSE", "walk_distance_m": np.nan, "walk_time_s": np.nan}
    return {"route_status": "OK", "walk_distance_m": float(props["totalDistance"]), "walk_time_s": float(props.get("totalTime", np.nan))}


def read_cache(path: Path) -> pd.DataFrame:
    """Cached routes; request errors are dropped so they are retried."""
    if not path.exists():
        return pd.DataFrame(columns=CACHE_COLUMNS)
    cache = pd.read_csv(path, dtype={"area_code": str, "cell_id": str})
    return cache[~cache.route_status.astype(str).str.startswith("REQUEST_ERROR")]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sbiz-zip", type=Path, required=True)
    parser.add_argument("--areas", type=Path, default=Path("data/processed/commercial_area_accessibility/commercial_area_candidates_25pct.geojson"))
    parser.add_argument("--cache", type=Path, required=True, help="저장소 밖 캐시 CSV (API 응답 커밋 금지)")
    parser.add_argument("--buffer-m", type=float, default=400)
    parser.add_argument("--max-calls", type=int, default=0, help="0이면 남은 전부")
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--dry-run", action="store_true", help="호출 없이 대상 수만 출력")
    parser.add_argument("--stratified", type=int, default=0, help="검증용: 직선 0-400m를 100m 구간 4개로 나눠 구간마다 같은 수를 무작위 추출")
    args = parser.parse_args()

    areas = gpd.read_file(args.areas).to_crs(5181)
    areas["area_code"] = areas.area_code.astype(str).str.zfill(7)
    # All stores, not only food/shopping: the specialisation index divides by
    # every store in the walk area, so numerator and denominator need the same rule.
    sbiz = read_sbiz_seoul(args.sbiz_zip)
    stores = gpd.GeoDataFrame(geometry=gpd.points_from_xy(sbiz["경도"], sbiz["위도"]), crs=4326).to_crs(5181)
    stores["cell_id"] = cell_id(stores.geometry.x, stores.geometry.y)
    cells = outside_cells(stores, areas, args.buffer_m)

    cache = read_cache(args.cache)
    done = set(zip(cache.area_code, cache.cell_id))
    todo = cells[[(a, c) not in done for a, c in zip(cells.area_code, cells.cell_id)]]
    if args.stratified:
        # Validation sample: equal draws from each 100m straight-line band, so
        # the hard cases near 400m are represented (nearest-first is not).
        band = (todo.euclidean_m // 100).clip(upper=3)
        per = args.stratified // 4
        todo = todo.groupby(band, group_keys=False).apply(lambda g: g.sample(min(per, len(g)), random_state=20261007))
    else:
        # Nearest cells first so a partial run already covers what matters most.
        todo = todo.sort_values("euclidean_m")
    print(f"cells {len(cells):,} / cached {len(done):,} / remaining {len(todo):,}", flush=True)
    if args.dry_run:
        return
    api_key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    if not api_key:
        sys.exit("KAKAO_REST_API_KEY is not set")
    if args.max_calls:
        todo = todo.head(args.max_calls)

    args.cache.parent.mkdir(parents=True, exist_ok=True)
    new_file = not args.cache.exists()
    session = requests.Session()
    calls = 0
    with args.cache.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CACHE_COLUMNS)
        if new_file:
            writer.writeheader()
        for row in todo.itertuples():
            try:
                route = fetch_walk_route(session, api_key, row)
            except PermissionError as error:
                print(f"stopped by API ({error}) after {calls:,} calls; rerun later to resume", flush=True)
                break
            except requests.RequestException as error:
                route = {"route_status": f"REQUEST_ERROR:{type(error).__name__}", "walk_distance_m": np.nan, "walk_time_s": np.nan}
            writer.writerow({"area_code": row.area_code, "cell_id": row.cell_id, "euclidean_m": row.euclidean_m, **route})
            calls += 1
            if calls % 500 == 0:
                handle.flush()
                print(f"{calls:,} calls", flush=True)
            time.sleep(args.sleep)
    print(f"done: {calls:,} new calls", flush=True)


if __name__ == "__main__":
    main()
