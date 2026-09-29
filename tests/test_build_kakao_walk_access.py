import pandas as pd


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, headers, params, timeout):
        self.calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return _Response(self.payload)


def test_fetch_walk_route_returns_distance_and_seconds_with_shortest_mode():
    from scripts.build_kakao_walk_access import fetch_walk_route

    session = _Session(
        {"status": "OK", "route": {"properties": {"totalDistance": 472, "totalTime": 401}}}
    )
    result = fetch_walk_route(session, "test-key", 127.0, 37.5, 127.01, 37.51)

    assert result == {"route_status": "OK", "walk_distance_m": 472.0, "walk_time_s": 401.0}
    assert session.calls[0]["headers"]["Authorization"] == "KakaoAK test-key"
    assert session.calls[0]["params"]["route_mode"] == "SHORTEST"


def test_fetch_walk_route_keeps_non_route_status_as_unknown():
    from scripts.build_kakao_walk_access import fetch_walk_route

    result = fetch_walk_route(_Session({"status": "ROUTE_RESULT_NOT_FOUND"}), "key", 1, 2, 3, 4)

    assert result["route_status"] == "ROUTE_RESULT_NOT_FOUND"
    assert pd.isna(result["walk_distance_m"])
