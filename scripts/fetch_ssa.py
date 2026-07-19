"""Download and atomically import the official SSA national name dataset."""

from __future__ import annotations

import argparse
import hashlib
import io
import sqlite3
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

SSA_NAMES_URL = "https://www.ssa.gov/oact/babynames/names.zip"


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "nobodynamed-video/0.2"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return response.read()


def _build_database(payload: bytes, destination: Path, source_url: str) -> tuple[int, int]:
    digest = hashlib.sha256(payload).hexdigest()
    temp_path = destination.with_suffix(destination.suffix + ".tmp")
    if temp_path.exists():
        temp_path.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(temp_path)
    try:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE names (
                name TEXT NOT NULL,
                sex TEXT NOT NULL CHECK(sex IN ('M','F')),
                year INTEGER NOT NULL,
                count INTEGER NOT NULL CHECK(count >= 5),
                PRIMARY KEY (name, sex, year)
            );
            CREATE INDEX idx_names_rank ON names(sex, year, count DESC, name ASC);
            CREATE TABLE dataset_metadata (
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                dataset_year INTEGER NOT NULL,
                imported_at TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                synthetic INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        years: list[int] = []
        row_count = 0
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for member in sorted(archive.namelist()):
                if not member.startswith("yob") or not member.endswith(".txt"):
                    continue
                year = int(Path(member).stem.removeprefix("yob"))
                years.append(year)
                rows: list[tuple[str, str, int, int]] = []
                text = archive.read(member).decode("utf-8")
                for line in text.splitlines():
                    name, sex, raw_count = line.split(",")
                    count = int(raw_count)
                    if count < 5:
                        raise ValueError(f"SSA row unexpectedly below reporting threshold: {line}")
                    rows.append((name, sex, year, count))
                conn.executemany(
                    "INSERT INTO names(name, sex, year, count) VALUES (?, ?, ?, ?)", rows
                )
                row_count += len(rows)
        if not years:
            raise ValueError("Archive contains no yobYYYY.txt files")
        latest_year = max(years)
        conn.execute(
            "INSERT INTO dataset_metadata VALUES (?, ?, ?, ?, ?, 0)",
            (
                "US Social Security Administration",
                source_url,
                latest_year,
                datetime.now(tz=UTC).isoformat(),
                digest,
            ),
        )
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
    except Exception:
        conn.close()
        if temp_path.exists():
            temp_path.unlink()
        raise
    else:
        conn.close()
    temp_path.replace(destination)
    return latest_year, row_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/ssa.sqlite"))
    parser.add_argument("--url", default=SSA_NAMES_URL)
    parser.add_argument("--source-zip", type=Path)
    args = parser.parse_args()
    payload = args.source_zip.read_bytes() if args.source_zip else _download(args.url)
    year, rows = _build_database(payload, args.out, args.url)
    print(f"Imported {rows:,} official SSA rows through {year} into {args.out}")


if __name__ == "__main__":
    main()
