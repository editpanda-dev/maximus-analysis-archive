#!/usr/bin/env python3
"""Download the official Seoul commercial-area source files used for subarea work."""

from __future__ import annotations

import argparse
import io
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


DOWNLOAD_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false"
FILES = {
    "commercial_area.zip": {"infId": "OA-15560", "seq": "5", "infSeq": "3"},
    "commercial_store_2025.zip": {"infId": "OA-15577", "seq": "20", "infSeq": "3"},
    "commercial_sales_2025.zip": {"infId": "OA-15572", "seq": "51", "infSeq": "3"},
}


def download_file(name: str, fields: dict[str, str], out_dir: Path) -> Path:
    request = urllib.request.Request(
        DOWNLOAD_URL,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise RuntimeError(f"{name}: expected zip file, received {data[:120]!r}")
    target = out_dir / name
    target.write_bytes(data)
    return target


def main() -> None:
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/commercial_area"))
    parser.add_argument("--only", choices=sorted(FILES), nargs="*")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    names = args.only or list(FILES)
    for name in names:
        path = download_file(name, FILES[name], args.output_dir)
        with zipfile.ZipFile(path) as archive:
            members = [member for member in archive.namelist() if not member.endswith("/")]
        print(f"downloaded {path} ({path.stat().st_size:,} bytes): {members}")


if __name__ == "__main__":
    main()
