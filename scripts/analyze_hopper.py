"""Run the data-first NobodyNamed hopper analysis against configured D1."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from nobodynamed_video.config import get_settings
from nobodynamed_video.data.d1_source import D1Source
from nobodynamed_video.research.hopper import analyze_candidates, load_candidates, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hopper", type=Path, help="YAML file containing candidate names")
    parser.add_argument("--out", type=Path, default=Path("out/hopper"), help="Report directory")
    parser.add_argument("--year", type=int, default=2025, help="Requested SSA reference year")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    if not settings.d1_url:
        raise SystemExit("D1_URL is required for hopper analysis")
    source = D1Source(settings.d1_url, settings.get_d1_token(), timeout=30.0)
    candidates = load_candidates(args.hopper)
    reference_year, results, errors = await analyze_candidates(candidates, source, args.year)
    json_path, markdown_path = write_report(
        args.out,
        reference_year,
        candidates,
        results,
        errors,
    )
    print(f"SSA reference year: {reference_year}")
    print(f"Scored: {len(results)}/{len(candidates)} candidate series")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    if errors:
        print(f"Retrieval errors: {len(errors)}")


if __name__ == "__main__":
    asyncio.run(main())
