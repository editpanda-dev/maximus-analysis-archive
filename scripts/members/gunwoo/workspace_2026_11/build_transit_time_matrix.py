#!/usr/bin/env python3
"""출발동(생활이동 통계동 중심) → 상권(786곳 중심) 대중교통 시간 행렬.

노선망: 저장소 scripts/build_seoul_transit_network.py로 만든 14시 버스·지하철망(데이터/가공/transit_network/)
경로 계산: 저장소 scripts/static_multimodal_accessibility.py의 route_from_access(다익스트라, 대기·환승 벌점 포함)
  출발 도보 600m, 환승 도보 250m, 걸음 1.2m/s, 버스 대기 5분, 지하철 대기 3분, 환승 벌점 2분 (저장소 기본값)
도착: 상권 중심 600m 안 정류장까지 걸은 시간을 더한 최솟값. 걸어서 가는 편이 빠르면 도보 시간(직선 × 1.3).
90분 안에 못 가면 90분으로 둔다(reachable=False).

실행: ~/.venvs/maximus/bin/python 분석/build_transit_time_matrix.py
"""

from __future__ import annotations

import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
REPO = HERE / "maximus-analysis-archive"
sys.path.insert(0, str(REPO / "scripts"))  # 저장소 스크립트는 형제 모듈을 직접 import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from static_multimodal_accessibility import (  # noqa: E402
    build_ride_adjacency, build_spatial_grid, build_walking_adjacency, nearby_stops, route_from_access)

NET = HERE / "데이터/가공/transit_network"
STATION_MASTER = REPO / "data/raw/seoul_station_master_20260902.csv"
# 저장소 지하철망은 서울교통공사 시간표라 1~9호선뿐이다. 코레일·민자 노선을 역 순서로 덧붙인다.
# (노선, 역 마스터의 호선 값들, 서울 구간 역 순서, 평균 대기 초 = 배차 절반)
EXTRA_LINES = [
    ("경의중앙", {"경의중앙선", "중앙선"}, ["수색", "디지털미디어시티", "가좌", "홍대입구", "서강대", "공덕", "효창공원앞", "용산",
                                     "이촌", "서빙고", "한남", "옥수", "응봉", "왕십리", "청량리", "회기", "중랑", "상봉", "망우", "양원"], 450),
    ("수인분당", {"분당선", "수인선"}, ["청량리", "왕십리", "서울숲", "압구정로데오", "강남구청", "선정릉", "선릉", "한티", "도곡",
                                 "구룡", "개포동", "대모산입구", "수서", "복정"], 240),
    ("경춘", {"경춘선"}, ["청량리", "회기", "중랑", "상봉", "망우", "신내"], 600),
    ("우이신설", {"우이신설선"}, ["북한산우이", "솔밭공원", "4.19민주묘지", "가오리", "화계", "삼양", "삼양사거리", "솔샘",
                              "북한산보국문", "정릉", "성신여대입구", "보문", "신설동"], 180),
    ("신림", {"신림선"}, ["샛강", "대방", "서울지방병무청", "보라매", "보라매공원", "보라매병원", "당곡", "신림", "서원",
                       "서울대벤처타운", "관악산"], 180),
    ("공항철도", {"공항철도1호선"}, ["서울역", "공덕", "홍대입구", "디지털미디어시티", "마곡나루", "김포공항"], 300),
    ("신분당", {"신분당선", "신분당선(연장)", "신분당선(연장2)"}, ["신사", "논현", "신논현", "강남", "양재", "양재시민의숲", "청계산입구"], 240),
]
RAIL_KMH = 36  # 정차 포함 평균 표정속도 가정
EXTRA = "--no-extra" not in sys.argv


def extra_rail() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    m = pd.read_csv(STATION_MASTER, encoding="cp949")
    stops, edges, waits = [], [], {}
    for line, codes, order, wait in EXTRA_LINES:
        sub = m[m["호선"].isin(codes)].drop_duplicates("역사명").set_index("역사명")
        # 환승역은 다른 호선으로만 올라 있을 수 있다 → 이름(괄호 앞)으로 아무 호선에서나 좌표를 가져온다
        anyline = m.assign(k=m["역사명"].str.split("(").str[0]).drop_duplicates("k").set_index("k")
        for s in order:
            if s not in sub.index and s in anyline.index:
                sub.loc[s] = anyline.loc[s, sub.columns]
        missing = [s for s in order if s not in sub.index]
        if missing:
            print(line, "역 마스터에 없음:", missing)
        seq = [s for s in order if s in sub.index]
        rid = f"rail_{line}"
        waits[rid] = wait
        for s in seq:
            stops.append({"stop_id": f"{rid}_{s}", "stop_name": s, "longitude": sub.at[s, "경도"], "latitude": sub.at[s, "위도"], "mode": "metro"})
        for a, b in zip(seq, seq[1:]):
            km = 6371 * 2 * np.arcsin(np.sqrt(np.sin(np.radians(sub.at[b, "위도"] - sub.at[a, "위도"]) / 2) ** 2
                                              + np.cos(np.radians(sub.at[a, "위도"])) * np.cos(np.radians(sub.at[b, "위도"]))
                                              * np.sin(np.radians(sub.at[b, "경도"] - sub.at[a, "경도"]) / 2) ** 2))
            sec = max(90, km / RAIL_KMH * 3600)
            for x, y in [(a, b), (b, a)]:
                edges.append({"route_id": rid, "from_stop_id": f"{rid}_{x}", "to_stop_id": f"{rid}_{y}", "duration_seconds": sec, "mode": "metro"})
    return pd.DataFrame(stops), pd.DataFrame(edges), waits
OUT = HERE / "데이터/가공/od_eval/transit_time_origin_area.csv"
CUTOFF_MIN = 90
WALK, ORIGIN_WALK_M, TRANSFER_WALK_M, DETOUR = 1.2, 600, 250, 1.3

_G: dict = {}


def _init() -> None:
    bus = pd.read_csv(NET / "bus_edges_14.csv", dtype={"route_id": str, "from_stop_id": str, "to_stop_id": str}).assign(mode="bus")
    metro = pd.read_csv(NET / "metro_edges.csv", dtype={"route_id": str, "from_stop_id": str, "to_stop_id": str}).assign(mode="metro")
    stops = pd.concat([pd.read_csv(NET / "bus_stops.csv", dtype={"stop_id": str}),
                       pd.read_csv(NET / "metro_stops.csv", dtype={"stop_id": str})]).drop_duplicates("stop_id").reset_index(drop=True)
    edges = pd.concat([bus, metro])
    waits: dict[str, int] = {}
    if EXTRA:
        xs, xe, waits = extra_rail()
        stops = pd.concat([stops, xs]).drop_duplicates("stop_id").reset_index(drop=True)
        edges = pd.concat([edges, xe])
    edges = edges[edges.from_stop_id.isin(stops.stop_id) & edges.to_stop_id.isin(stops.stop_id)]
    _G.update(waits=waits, stops=stops, grid=build_spatial_grid(stops), ride=build_ride_adjacency(edges),
              walk=build_walking_adjacency(stops, TRANSFER_WALK_M, WALK))
    from eval_generalization import area_centroids  # noqa: E402
    import build_serendipity_ranking as serp  # noqa: E402
    area, _ = serp.load_inputs(REPO, 20254, use_movement=True)
    a = area[["area_code"]].merge(area_centroids(), on="area_code")
    # 상권별 도착 정류장(걸은 초)
    _G["area"] = a
    _G["egress"] = [nearby_stops(r.lon, r.lat, stops, _G["grid"], ORIGIN_WALK_M, WALK) for r in a.itertuples()]


def _one(args) -> list[dict]:
    origin, lat, lon = args
    s = _G["stops"]
    access = nearby_stops(lon, lat, s, _G["grid"], ORIGIN_WALK_M, WALK)
    reach = route_from_access(_G["ride"], _G["walk"], access, CUTOFF_MIN * 60, {"bus": 300, "metro": 180}, 120, _G["waits"])
    a = _G["area"]
    walk_direct = 6371000 * 2 * np.arcsin(np.sqrt(
        np.sin(np.radians(a.lat - lat) / 2) ** 2 + np.cos(np.radians(lat)) * np.cos(np.radians(a.lat)) * np.sin(np.radians(a.lon - lon) / 2) ** 2)) * DETOUR / WALK
    rows = []
    for i, r in enumerate(a.itertuples()):
        t = min((reach[k] + w for k, w in _G["egress"][i].items() if k in reach), default=np.inf)
        t = min(t, walk_direct.iloc[i])
        rows.append({"origin": origin, "area_code": r.area_code, "transit_min": min(t / 60, CUTOFF_MIN),
                     "reachable": bool(t / 60 <= CUTOFF_MIN)})
    return rows


def main() -> None:
    from eval_generalization import load_common
    _, _, origin_xy, *_ = load_common()
    jobs = [(o, r.lat, r.lon) for o, r in origin_xy.iterrows() if str(o).startswith("11")]
    print("출발동", len(jobs))
    with Pool(8, initializer=_init) as p:
        out = []
        for i, rows in enumerate(p.imap_unordered(_one, jobs, chunksize=4), 1):
            out += rows
            if i % 50 == 0:
                print(i, flush=True)
    df = pd.DataFrame(out)
    df.to_csv(OUT if EXTRA else OUT.with_name(OUT.stem + "_1to9.csv"), index=False)
    print(df.transit_min.describe().round(1).to_dict(), "도달 못함", (~df.reachable).mean().round(3))


if __name__ == "__main__":
    main()
