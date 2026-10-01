#!/usr/bin/env python3
"""Map B078 250m OD cells to Seoul administrative dongs and build a secure-safe mart."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / "tmp" / "eda_deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))
from pyproj import Transformer


PURPOSE_MAP = {1: "출근", 2: "등교", 3: "귀가", 4: "쇼핑", 5: "관광", 6: "병원", 7: "기타"}
REQUIRED = {"ETL_YMD", "O_CELL_ID", "O_CELL_X", "O_CELL_Y", "D_CELL_ID", "D_CELL_X", "D_CELL_Y",
            "ST_TIME_CD", "FNS_TIME_CD", "IN_FORN_DIV_NM", "MOVE_PURPOSE", "MOVE_DIST", "MOVE_TIME"}


def read_csv_auto(path: Path, **kwargs) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 확인할 수 없습니다: {path}")


def parse_demographic_column(column: str):
    match = re.fullmatch(r"(MALE|FEML)_(\d{2})_CNT", column)
    if not match:
        return None
    sex = "남성" if match.group(1) == "MALE" else "여성"
    age = int(match.group(2))
    band = f"{age // 10 * 10}대" if age < 60 else "60대이상"
    return sex, band


def add_b078_derived_fields(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    count_cols = [c for c in out if parse_demographic_column(c)]
    out["movement_total"] = out[count_cols].sum(axis=1, min_count=1)
    out["move_time_min"] = pd.to_numeric(out["MOVE_TIME"], errors="coerce")  # official unit: minutes
    out["move_distance_m"] = pd.to_numeric(out["MOVE_DIST"], errors="coerce")
    out["purpose_name"] = pd.to_numeric(out["MOVE_PURPOSE"], errors="coerce").map(PURPOSE_MAP).fillna("미상")
    for sex in ("남성", "여성"):
        for band in ("0대", "10대", "20대", "30대", "40대", "50대", "60대이상"):
            cols = [c for c in count_cols if parse_demographic_column(c) == (sex, band)]
            out[f"{sex}_{band}_이동량"] = out[cols].sum(axis=1) if cols else 0.0
    return out


def _polygon_contains(lon: float, lat: float, geometry: dict) -> bool:
    def one(poly):
        if not MplPath(np.asarray(poly[0], dtype=float)).contains_point((lon, lat), radius=1e-12):
            return False
        return not any(MplPath(np.asarray(hole, dtype=float)).contains_point((lon, lat), radius=1e-12) for hole in poly[1:])
    if geometry["type"] == "Polygon":
        return one(geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return any(one(poly) for poly in geometry["coordinates"])
    return False


def load_boundaries(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for feature in data["features"]:
        coords = feature["geometry"]["coordinates"]
        flat = []
        if feature["geometry"]["type"] == "Polygon":
            flat = coords[0]
        elif feature["geometry"]["type"] == "MultiPolygon":
            flat = [point for poly in coords for point in poly[0]]
        xs, ys = zip(*flat)
        records.append((min(xs), min(ys), max(xs), max(ys), feature))
    return records


def lookup_dong(lon: float, lat: float, boundaries):
    for minx, miny, maxx, maxy, feature in boundaries:
        if minx <= lon <= maxx and miny <= lat <= maxy and _polygon_contains(lon, lat, feature["geometry"]):
            p = feature["properties"]
            return p.get("emd8"), p.get("emdnm"), p.get("sggnm")
    return None, None, None


def build_crosswalk(frame: pd.DataFrame, boundary_path: Path) -> pd.DataFrame:
    origin = frame[["O_CELL_ID", "O_CELL_X", "O_CELL_Y"]].rename(columns=lambda c: c.replace("O_", ""))
    dest = frame[["D_CELL_ID", "D_CELL_X", "D_CELL_Y"]].rename(columns=lambda c: c.replace("D_", ""))
    cells = pd.concat([origin, dest], ignore_index=True).drop_duplicates("CELL_ID")
    transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(cells["CELL_X"].to_numpy(), cells["CELL_Y"].to_numpy())
    cells["lon"], cells["lat"] = lon, lat
    boundaries = load_boundaries(boundary_path)
    matched = [lookup_dong(x, y, boundaries) for x, y in zip(lon, lat)]
    cells[["admin_code", "dong_name", "sggnm"]] = pd.DataFrame(matched, index=cells.index)
    cells["match_status"] = np.where(cells["admin_code"].notna(), "matched", "outside_or_unmatched")
    return cells.sort_values("CELL_ID").reset_index(drop=True)


def run(args) -> None:
    source = Path(args.input)
    frame = read_csv_auto(source, low_memory=False)
    missing = sorted(REQUIRED - set(frame.columns))
    if missing:
        raise ValueError(f"필수 열 누락: {missing}")
    frame = add_b078_derived_fields(frame)
    crosswalk = build_crosswalk(frame, Path(args.boundary))
    cw = crosswalk.set_index("CELL_ID")
    for prefix in ("O", "D"):
        frame[f"{prefix}_ADMIN_CODE"] = frame[f"{prefix}_CELL_ID"].map(cw["admin_code"])
        frame[f"{prefix}_DONG_NAME"] = frame[f"{prefix}_CELL_ID"].map(cw["dong_name"])
        frame[f"{prefix}_SGGNM"] = frame[f"{prefix}_CELL_ID"].map(cw["sggnm"])

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(output / "b078_cell_admin_dong_crosswalk.csv", index=False, encoding="utf-8-sig")
    frame.to_csv(output / "b078_mapped_rows.csv", index=False, encoding="utf-8-sig")

    demo_cols = [c for c in frame if c.endswith("_이동량")]
    keys = ["ETL_YMD", "ST_TIME_CD", "FNS_TIME_CD", "O_ADMIN_CODE", "O_DONG_NAME", "O_SGGNM",
            "D_ADMIN_CODE", "D_DONG_NAME", "D_SGGNM", "IN_FORN_DIV_NM", "MOVE_PURPOSE", "purpose_name"]
    valid = frame.dropna(subset=["O_ADMIN_CODE", "D_ADMIN_CODE"]).copy()
    valid["weighted_time"] = valid["move_time_min"] * valid["movement_total"]
    valid["weighted_distance"] = valid["move_distance_m"] * valid["movement_total"]
    mart = valid.groupby(keys, as_index=False, dropna=False).agg(
        movement_total=("movement_total", "sum"), weighted_time=("weighted_time", "sum"),
        weighted_distance=("weighted_distance", "sum"), **{c: (c, "sum") for c in demo_cols}
    )
    mart["move_time_min"] = mart["weighted_time"] / mart["movement_total"].replace(0, np.nan)
    mart["move_distance_m"] = mart["weighted_distance"] / mart["movement_total"].replace(0, np.nan)
    mart = mart.drop(columns=["weighted_time", "weighted_distance"])
    mart.to_csv(output / "b078_dong_od_mart.csv", index=False, encoding="utf-8-sig")

    target = mart[(mart["O_SGGNM"] == "동대문구") & (mart["move_time_min"] <= args.max_minutes)].copy()
    target.to_csv(output / f"dongdaemun_origin_within_{args.max_minutes}min.csv", index=False, encoding="utf-8-sig")
    destination = target.groupby(["D_ADMIN_CODE", "D_DONG_NAME", "D_SGGNM", "purpose_name"], as_index=False).agg(
        movement_total=("movement_total", "sum"), median_time_min=("move_time_min", "median")
    ).sort_values("movement_total", ascending=False)
    destination.to_csv(output / f"dongdaemun_{args.max_minutes}min_destination_purpose.csv", index=False, encoding="utf-8-sig")

    audit = {
        "source_file": source.name, "source_rows": len(frame), "source_is_sample": "sample" in source.name.lower(),
        "move_time_unit": "minutes", "purpose_codes": PURPOSE_MAP,
        "unique_cells": len(crosswalk), "matched_cells": int(crosswalk.admin_code.notna().sum()),
        "cell_match_rate": float(crosswalk.admin_code.notna().mean()),
        "both_endpoints_matched_rows": len(valid), "mapped_row_rate": float(len(valid) / len(frame)) if len(frame) else 0,
        "dongdaemun_origin_rows": int((frame.O_SGGNM == "동대문구").sum()),
        f"dongdaemun_within_{args.max_minutes}min_rows": len(target),
        "boundary_reference_date": "2026-07-01",
        "boundary_time_mismatch_warning": "B078 2024 sample and 2026 boundary differ; use a period-matched crosswalk for final inference.",
    }
    (output / "b078_mapping_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/external/B078_PURPOSE_250M_202403_sample.csv")
    p.add_argument("--boundary", default="data/external/seoul_administrative_dongs_20260701.geojson")
    p.add_argument("--output", default="data/processed/b078_dong_mart")
    p.add_argument("--max-minutes", type=int, default=30)
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
