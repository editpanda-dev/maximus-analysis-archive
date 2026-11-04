"""GBIS 노선·정류소로 캠퍼스 출발 버스 이동시간을 추정한다 (ODsay 한도 초과 시 대체).

시간표가 없으므로 RAPTOR처럼 '라운드마다 한 번 더 탄다' 방식으로 계산한다.
    도보     = 직선 × 1.25 ÷ 시속 4.5km (출발·환승·도착). 캠퍼스에서 바로 걷는 건 직선 1km까지만
    승차     = 정류소 간 직선거리 ÷ 노선유형별 속도 (ODsay 10-28 실측 15개 동으로 보정)
    환승     = 300m 안 정류소로 걸어가 다시 탐, 1회당 고정 벌점
    대기     = 기본은 넣지 않음 (ODsay totalTime과 같은 정의). wait=True면 노선 비첨두 배차의 절반(최대 30분)
지하철(경강선)은 GBIS에 없어 빠진다. 30분 안 결과에는 영향이 거의 없다(10-28 경강선 경로는 모두 60분 이상).
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

RAW = (Path(os.environ["MAXIMUS_WORKSPACE"]) if "MAXIMUS_WORKSPACE" in os.environ else next(p for p in Path(__file__).resolve().parents if (p / "데이터").is_dir())) / "데이터/원천/모현"
CAMPUS = (37.33707, 127.26543)
WALK_DETOUR, WALK_KMH = 1.25, 4.5
ORIGIN_WALK_M, DEST_WALK_M, TRANSFER_WALK_M = 800, 600, 300
# 캠퍼스에서 버스 없이 바로 걷는 건 직선 1km까지만. 산지라 그 너머는 직선×1.25가 크게 틀린다
# (10-29 카카오 보행경로: 직선 1.2km 매산저수지 59분, 1.4km 갈월계곡 71분)
DIRECT_WALK_MAX_M = 1000
WAIT_CAP_MIN = 30  # 배차 120분짜리 마을버스도 시간표를 보고 나간다고 보고 대기는 30분까지만
ROUNDS = 3  # 최대 3번 탑승(환승 2회)
EXPRESS_TYPES = {"11", "12", "14", "16", "17", "21", "22"}  # 직행좌석·좌석·광역급행 등


def _read(name: str) -> pd.DataFrame:
    raw = (RAW / "gbis" / name).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")
    return pd.read_csv(io.StringIO(text.replace("^", "\n")), sep="|", dtype=str)


def _xy_m(lat, lon):
    """캠퍼스 중심 근사 평면좌표(m). 수십 km 안에서는 충분하다."""
    return np.c_[(np.asarray(lon, float) - CAMPUS[1]) * 88_600, (np.asarray(lat, float) - CAMPUS[0]) * 111_000]


def walk_min(dist_m):
    return np.asarray(dist_m) * WALK_DETOUR / (WALK_KMH * 1000) * 60


class BusNetwork:
    def __init__(self, radius_km: float = 25):
        rs = _read("routestation20261029V2.txt").dropna(subset=["x", "y"])
        rs = rs[rs.routeId != "routeId"]
        routes = _read("route20261029V2.txt").drop_duplicates("routeId").set_index("routeId")
        rs["express"] = rs.routeId.map(routes.routeTypeCd).isin(EXPRESS_TYPES)
        # 비첨두 배차(분). 공강·오후 이동 기준. 값이 없으면 첨두 배차, 그것도 없으면 30분으로 둔다
        headway = pd.to_numeric(routes.npeekAlloc, errors="coerce").where(lambda h: h > 0)
        headway = headway.fillna(pd.to_numeric(routes.peekAlloc, errors="coerce").where(lambda h: h > 0)).fillna(30)
        rs["headway"] = rs.routeId.map(headway)
        rs["staOrder"] = rs.staOrder.astype(int)
        xy = _xy_m(rs.y, rs.x)
        rs["mx"], rs["my"] = xy[:, 0], xy[:, 1]
        near = rs.groupby("routeId").apply(lambda g: np.hypot(g.mx, g.my).min() <= radius_km * 1000, include_groups=False)
        rs = rs[rs.routeId.isin(near[near].index)]
        stops = rs.drop_duplicates("stationId").reset_index(drop=True)
        self.stop_index = pd.Series(stops.index, index=stops.stationId)
        self.stop_xy = stops[["mx", "my"]].to_numpy()
        self.tree = cKDTree(self.stop_xy)
        self.patterns = []  # (정류소 번호 배열, 구간거리 배열, 급행 여부, 배차 분)
        for (_, _), g in rs.sort_values("staOrder").groupby(["routeId", "upDown"]):
            idx = self.stop_index[g.stationId].to_numpy()
            seg = np.hypot(np.diff(g.mx.to_numpy()), np.diff(g.my.to_numpy()))
            self.patterns.append((idx, seg, bool(g.express.iat[0]), float(g.headway.iat[0])))
        pairs = self.tree.query_pairs(TRANSFER_WALK_M, output_type="ndarray")
        self.transfer = pairs, walk_min(np.hypot(*(self.stop_xy[pairs[:, 0]] - self.stop_xy[pairs[:, 1]]).T))

    def stop_times(self, local_kmh: float, express_kmh: float, transfer_min: float, wait: bool = False) -> np.ndarray:
        """캠퍼스에서 각 정류소까지 최소 분(정류소에 내려 서 있는 시각).

        wait=True면 탈 때마다 그 노선 배차의 절반(최대 WAIT_CAP_MIN)을 기다린다고 본다(시간표를 모를 때의 기대 대기).
        """
        n = len(self.stop_xy)
        best = np.full(n, np.inf)
        d0 = np.hypot(self.stop_xy[:, 0], self.stop_xy[:, 1])
        reach = np.where(d0 <= ORIGIN_WALK_M, walk_min(d0), np.inf)  # 탈 수 있는 시각
        for r in range(ROUNDS):
            board = reach + (transfer_min if r else 0)
            arrive = np.full(n, np.inf)
            for idx, seg, express, headway in self.patterns:
                minutes = seg / ((express_kmh if express else local_kmh) * 1000) * 60
                w = min(headway / 2, WAIT_CAP_MIN) if wait else 0.0
                t = np.inf
                for k, s in enumerate(idx):
                    if k:
                        t += minutes[k - 1]
                        if t < arrive[s]:
                            arrive[s] = t
                    if board[s] + w < t:
                        t = board[s] + w
            best = np.minimum(best, arrive)
            # 내린 정류소에서 걸어서 갈 수 있는 정류소까지 다음 라운드 탑승 후보
            nxt = arrive.copy()
            pairs, w = self.transfer
            a, b = pairs[:, 0], pairs[:, 1]
            np.minimum.at(nxt, b, arrive[a] + w)
            np.minimum.at(nxt, a, arrive[b] + w)
            reach = nxt
        return best

    def to_points(self, stop_min: np.ndarray, lat, lon) -> np.ndarray:
        """목적지 점까지: 내린 정류소 + 도보, 또는 캠퍼스에서 바로 도보 중 짧은 쪽."""
        pts = _xy_m(lat, lon)
        d0 = np.hypot(pts[:, 0], pts[:, 1])
        out = np.where(d0 <= DIRECT_WALK_MAX_M, walk_min(d0), np.inf)
        for i, near in enumerate(self.tree.query_ball_point(pts, DEST_WALK_M)):
            if near:
                near = np.asarray(near)
                out[i] = min(out[i], (stop_min[near] + walk_min(np.hypot(*(self.stop_xy[near] - pts[i]).T))).min())
        return out


def calibrate(net: BusNetwork, targets: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """targets: lat, lon, odsay_min. 평균절대오차가 가장 작은 속도·환승 벌점을 고른다."""
    best = None
    for local in (10, 12, 14, 16, 18, 20):
        for express in (14, 16, 18, 20, 24, 28):
            for tr in (2, 4, 6, 8):
                est = net.to_points(net.stop_times(local, express, tr), targets.lat, targets.lon)
                mae = np.abs(est - targets.odsay_min).mean()
                if best is None or mae < best[0]:
                    best = (mae, {"local_kmh": local, "express_kmh": express, "transfer_min": tr}, est)
    mae, params, est = best
    params["mae_min"] = round(float(mae), 1)
    return params, targets.assign(est_min=est.round(1))
