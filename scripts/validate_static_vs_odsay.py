#!/usr/bin/env python3
"""Compare cached ODsay 30-minute isochrones with static-model reached stops.

ODsay cache records only an isochrone polygon, not a route-time table.  This
therefore validates the same decision that drives candidate generation: whether
each stop falls inside a 30-minute reachable area. It does not claim route-level
minute error or real-time agreement.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape
from shapely.ops import unary_union


def isochrone_geometry(payload: dict):
    features = payload.get("result", {}).get("geojson", {}).get("features", [])
    geometries = [shape(feature["geometry"]) for feature in features if feature.get("geometry")]
    if not geometries:
        raise ValueError("ODsay payload has no GeoJSON features")
    return unary_union(geometries)


def compare_origin(origin_id: str, stops: pd.DataFrame, static_reached: pd.DataFrame, payload: dict) -> dict:
    geometry = isochrone_geometry(payload)
    odsay_ids = set(
        stops.loc[
            [geometry.covers(Point(row.longitude, row.latitude)) for row in stops.itertuples(index=False)],
            "stop_id",
        ].astype(str)
    )
    static_ids = set(static_reached.loc[static_reached["origin_id"].astype(str) == str(origin_id), "stop_id"].astype(str))
    tp = len(odsay_ids & static_ids)
    fp = len(static_ids - odsay_ids)
    fn = len(odsay_ids - static_ids)
    return {
        "origin_id": str(origin_id),
        "odsay_reached_stops": len(odsay_ids),
        "static_reached_stops": len(static_ids),
        "true_positive_stops": tp,
        "false_positive_stops": fp,
        "false_negative_stops": fn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "jaccard": tp / (tp + fp + fn) if tp + fp + fn else 0.0,
    }


def load_stops(network_dir: Path) -> pd.DataFrame:
    bus = pd.read_csv(network_dir / "bus_stops.csv", dtype={"stop_id": str})
    metro = pd.read_csv(network_dir / "metro_stops.csv", dtype={"stop_id": str})
    return pd.concat([bus, metro], ignore_index=True).drop_duplicates("stop_id").dropna(subset=["longitude", "latitude"])


def run(args: argparse.Namespace) -> None:
    cache_dir = Path(args.cache_dir)
    static_root = Path(args.static_root)
    stops = load_stops(Path(args.network_dir))
    payloads = {}
    for path in sorted(cache_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            isochrone_geometry(payload)
            payloads[path.stem] = payload
        except (json.JSONDecodeError, ValueError, KeyError):
            continue
    if not payloads:
        raise SystemExit("no valid cached ODsay isochrones found")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_rows = []
    all_rows = []
    for hour in args.hours:
        static = pd.read_csv(static_root / f"h{hour:02d}" / "reachable_stops_by_origin.csv", dtype={"origin_id": str, "stop_id": str})
        available = sorted(set(payloads).intersection(set(static["origin_id"])))
        for origin_id in available:
            row = compare_origin(origin_id, stops, static, payloads[origin_id])
            row["hour"] = hour
            all_rows.append(row)
        frame = pd.DataFrame([r for r in all_rows if r["hour"] == hour])
        report_rows.append({
            "hour": hour,
            "cached_origins": len(frame),
            "mean_precision": frame["precision"].mean(),
            "median_precision": frame["precision"].median(),
            "mean_recall": frame["recall"].mean(),
            "median_recall": frame["recall"].median(),
            "mean_jaccard": frame["jaccard"].mean(),
            "median_jaccard": frame["jaccard"].median(),
        })

    detail = pd.DataFrame(all_rows).sort_values(["hour", "jaccard", "origin_id"])
    summary = pd.DataFrame(report_rows)
    detail.to_csv(out / "odsay_static_stop_overlap_detail.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "odsay_static_stop_overlap_summary.csv", index=False, encoding="utf-8-sig")
    best_hour = summary.sort_values("mean_jaccard", ascending=False).iloc[0]
    lines = [
        "# ODsay 캐시 대비 정적 교통망 30분 도달 판정 검증",
        "",
        "## 검증 대상",
        "",
        f"ODsay의 저장된 30분 등시간 폴리곤과 동일 출발지의 정적 교통망 도달 정류장을 비교했다. 유효 캐시는 {len(payloads)}개이며, 이 중 정적 출발지 목록과 일치한 {summary['cached_origins'].max()}개를 비교했다. 각 정류장 좌표가 폴리곤 안에 있는지로 ODsay 도달 정류장 집합을 만들었다.",
        "",
        "## 결과",
        "",
        "|시간대|캐시 출발지|평균 Precision|평균 Recall|평균 Jaccard|",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in report_rows:
        lines.append(f"|{row['hour']:02d}시|{row['cached_origins']}|{row['mean_precision']:.3f}|{row['mean_recall']:.3f}|{row['mean_jaccard']:.3f}|")
    lines += [
        "",
        "## 해석",
        "",
        f"세 시간대 중 평균 Jaccard가 가장 높은 비교는 {int(best_hour['hour']):02d}시({best_hour['mean_jaccard']:.3f})였다. Precision은 정적 모형이 도달 가능하다고 한 정류장 중 ODsay 폴리곤에도 포함된 비율이고, Recall은 ODsay 폴리곤 안 정류장 중 정적 모형이 잡은 비율이다.",
        "",
        "이 결과는 폴리곤 기반 30분 판정의 표본 일치도다. ODsay가 개별 OD 경로의 출발시각·세부 환승·실시간 도착정보를 제공한 비교가 아니므로 분 단위 오차나 실시간 정확도로 해석하지 않는다. 캐시 출발지가 전체 334개를 대표하지 않을 수 있으므로, 상위 후보의 개별 OD 경로 조회를 추가 검증으로 남긴다.",
    ]
    (out / "ODSAY_STATIC_VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default="data/interim/odsay_30min/raw")
    parser.add_argument("--network-dir", default="data/interim/local_transit")
    parser.add_argument("--static-root", default="data/processed/local_transit_30min")
    parser.add_argument("--hours", type=int, nargs="+", default=[8, 14, 19])
    parser.add_argument("--output-dir", default="data/processed/transit_validation")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
