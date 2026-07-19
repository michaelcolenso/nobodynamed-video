"""Create a human-uploadable, source-backed release directory."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nobodynamed_video.models import RenderManifest, VideoSpec


def source_note(spec: VideoSpec) -> str:
    provenance = spec.record.provenance
    if provenance is None:
        return "Source provenance unavailable. This artifact is not publishable."
    threshold = provenance.reporting_threshold
    note = (
        f"Source: {provenance.source}, dataset through {provenance.dataset_year}. "
        f"SSA publishes national name rows only when at least {threshold} births are recorded; "
        "an absent row does not prove zero births."
    )
    if provenance.source_url:
        note += f" {provenance.source_url}"
    if provenance.synthetic:
        note = "TEST/PREVIEW ONLY — synthetic data. " + note
    return note


def package_release(
    spec: VideoSpec,
    manifest: RenderManifest,
    out_dir: Path,
    release_root: Path,
) -> Path:
    release_dir = release_root / spec.id
    release_dir.mkdir(parents=True, exist_ok=True)
    mp4 = Path(manifest.output_path)
    cover = out_dir / spec.id / "frames" / "hook_000.png"
    manifest_path = out_dir / f"{spec.id}.json"
    shutil.copy2(mp4, release_dir / f"{spec.id}.mp4")
    shutil.copy2(cover, release_dir / "cover.png")
    shutil.copy2(manifest_path, release_dir / "manifest.json")
    captions = out_dir / spec.id / "captions.srt"
    if captions.exists():
        shutil.copy2(captions, release_dir / "captions.srt")

    context = spec.context
    hook = spec.hook
    claims = [claim.model_dump(mode="json") for claim in (context.claims if context else [])]
    (release_dir / "claims.json").write_text(json.dumps(claims, indent=2) + "\n")
    (release_dir / "caption.txt").write_text((manifest.caption or "") + "\n")
    (release_dir / "pinned-comment.txt").write_text((manifest.pinned_comment or "") + "\n")
    transcript_parts = [
        hook.headline if hook else "",
        hook.subhead if hook else "",
        context.narrative_text if context else "",
        context.supporting_text if context and context.supporting_text else "",
        "Run your name at nobodynamed.com.",
    ]
    transcript = "\n".join(part for part in transcript_parts if part)
    (release_dir / "transcript.txt").write_text(transcript + "\n")
    (release_dir / "source-note.md").write_text(source_note(spec) + "\n")
    alt = (
        f"Vertical data-story video about the name {spec.record.name}, showing recorded "
        f"SSA births from {spec.record.series[0].year} through {spec.record.current_year}."
    )
    (release_dir / "alt-text.txt").write_text(alt + "\n")
    return release_dir
