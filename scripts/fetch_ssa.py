"""Extract reproducible selected-name snapshots from the complete official SSA ZIP.

Usage: uv run python scripts/fetch_ssa.py /path/names.zip --year 2025 --out data/ssa-2025
Download: https://www.ssa.gov/oact/babynames/names.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile


def extract(archive: Path, year: int, out: Path, names: list[str]) -> None:
    selected = [tuple(item.split(':')) for item in names]
    observations: dict[str, list[dict[str, int | None]]] = {n: [] for n, _ in selected}
    with ZipFile(archive) as z:
        for y in range(1880, year + 1):
            rows = [line.split(',') for line in z.read(f'yob{y}.txt').decode().splitlines()]
            counts = {(n, sex): int(count) for n, sex, count in rows}
            for name, sex in selected:
                count = counts.get((name, sex))
                rank = (1 + sum(int(c) > count for _, s, c in rows if s == sex)
                        if count is not None else None)
                observations[name].append({'year': y, 'count': count, 'rank': rank})
    out.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    retrieved_at = datetime.now(UTC).isoformat()
    for name, sex in selected:
        payload = {'schema_version': 1, 'source_url': 'https://www.ssa.gov/oact/babynames/names.zip',
                   'archive_sha256': sha, 'retrieved_at': retrieved_at, 'name': name,
                   'sex': sex, 'latest_year': year, 'observations': observations[name]}
        target = out / f'{name.lower()}-{sex.lower()}.json'
        target.write_text(json.dumps(payload, indent=2) + '\n')
        print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--names', nargs='+', default=[
        'Alexa:F', 'Hazel:F', 'Bertha:F', 'Kunta:M', 'Jennifer:F', 'Eleanor:F'])
    args = parser.parse_args()
    extract(args.archive, args.year, args.out, args.names)
