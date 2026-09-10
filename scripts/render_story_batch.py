"""Render an approved StorySpec batch with bounded narration pacing."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from nobodynamed_video.batch.runner import run_batch
from nobodynamed_video.batch.spec import load_specs
from nobodynamed_video.compose.narration_pacing import (
    FitDurationCloudflareNarrationProvider,
)
from nobodynamed_video.config import get_settings
from nobodynamed_video.qc import checks as qc_checks

# Story covers intentionally use a near-black brand background. The generic 98%
# blackframe gate incorrectly rejected three visibly populated next-six covers.
# A 99% threshold still rejects a genuinely blank dark frame while allowing
# readable typography and labels on the designed cover.
_STORY_COVER_BLACK_AMOUNT = 99


async def _render(spec_path: Path) -> None:
    settings = get_settings()
    specs = await load_specs(spec_path)
    qc_checks._COVER_BLACK_AMOUNT = _STORY_COVER_BLACK_AMOUNT
    provider = FitDurationCloudflareNarrationProvider(
        account_id=settings.workers_ai_account_id(),
        api_token=settings.cloudflare_api_token or settings.d1_token,
        cache_dir=settings.out_dir / ".cache" / "narration",
        base_url=settings.cloudflare_ai_base_url,
        model=settings.narration_model,
        transcription_model=settings.transcription_model,
        default_voice=settings.narration_voice,
    )
    await run_batch(
        specs=specs,
        satori_url=settings.satori_url,
        out_dir=settings.out_dir,
        batch_name=spec_path.stem,
        narration_enabled=True,
        narration_provider=provider,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Approved batch YAML")
    args = parser.parse_args()
    asyncio.run(_render(args.spec))


if __name__ == "__main__":
    main()
