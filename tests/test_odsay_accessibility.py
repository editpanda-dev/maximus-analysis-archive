import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "odsay_accessibility.py"
SPEC = importlib.util.spec_from_file_location("odsay_accessibility", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_extract_geojson():
    geojson = {"type": "FeatureCollection", "features": [{"type": "Feature"}]}
    assert MODULE.extract_geojson({"result": {"geojson": geojson}}) == geojson


def test_extract_geojson_formats_list_error():
    payload = {"error": [{"code": "429", "message": "Daily quota exceeded"}]}
    with pytest.raises(RuntimeError, match="ODsay error 429: Daily quota exceeded"):
        MODULE.extract_geojson(payload)


def test_load_cached_payload_quarantines_error(tmp_path):
    path = tmp_path / "origin.json"
    path.write_text('{"error":[{"code":"429","message":"Daily quota exceeded"}]}')
    assert MODULE.load_cached_payload(path) is None
    assert not path.exists()
    assert (tmp_path / "origin.error.json").exists()


def test_merge_adds_origin_metadata_without_mutating_input():
    geojson = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": None}],
    }
    result = MODULE.merge_feature_collections(
        [({"origin_id": "a", "origin_name": "회기역"}, geojson)]
    )
    assert result["features"][0]["properties"]["origin_id"] == "a"
    assert geojson["features"][0]["properties"] == {}


def test_read_origins(tmp_path):
    path = tmp_path / "origins.csv"
    path.write_text(
        "origin_id,origin_name,longitude,latitude\na,회기역,127.05,37.59\n",
        encoding="utf-8",
    )
    rows = MODULE.read_origins(path)
    assert rows[0]["longitude"] == 127.05


def test_system_trust_store_is_optional(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "truststore", None)
    MODULE.install_system_trust_store()
