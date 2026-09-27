"""Render a long-form episode: title card, approved chapters, closing card, one master."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol

from rich.console import Console
from ruamel.yaml import YAML

from nobodynamed_video.batch.runner import _renderer_digest, render_spec
from nobodynamed_video.batch.spec import load_specs
from nobodynamed_video.compose.caption import combo_hash
from nobodynamed_video.compose.ffmpeg import (
    build_concat_cmd,
    build_ffmpeg_cmd,
    get_ffmpeg_version,
    run_ffmpeg,
)
from nobodynamed_video.compose.lexicon import Lexicon
from nobodynamed_video.compose.narration import NarrationArtifact
from nobodynamed_video.compose.narration_pacing import fit_narration_audio
from nobodynamed_video.compose.state import CombinationState
from nobodynamed_video.data.snapshot import verified_snapshot
from nobodynamed_video.editorial.story import chapter_narration_text
from nobodynamed_video.exceptions import StoryQualityError
from nobodynamed_video.longform.bookends import (
    MAX_BOOKEND_NARRATION_S,
    bookend_duration,
    sample_bookend_frame,
)
from nobodynamed_video.longform.spec import (
    MAX_EPISODE_S,
    MIN_EPISODE_S,
    RosterEntry,
    aggregate_total,
    evaluate_longform,
    load_longform,
    roster_entry,
)
from nobodynamed_video.models import LongFormBookend, LongFormSpec, StorySpec
from nobodynamed_video.qc.checks import run_all_checks, run_longform_checks
from nobodynamed_video.render.golden import sha256_bytes
from nobodynamed_video.render.satori_client import SatoriClient

console = Console()

_CAPTIONS_YAML = Path("fixtures/captions.yaml")
_STATE_DB = Path("state/used_combinations.db")
_NARRATION_CODES = frozenset({"NARRATION", "AI_DISCLOSURE"})


class EpisodeNarrator(Protocol):
    async def generate(self, story: StorySpec) -> NarrationArtifact: ...

    async def generate_text(self, text: str, voice: str | None = None) -> NarrationArtifact: ...


class ChapterNarrator:
    """Narrate a chapter without its short-form loop beat, with the chapter pace fit."""

    def __init__(self, inner: EpisodeNarrator) -> None:
        self._inner = inner

    async def generate(self, story: StorySpec) -> NarrationArtifact:
        artifact = await self._inner.generate_text(chapter_narration_text(story), story.voice)
        return fit_narration_audio(artifact)


def _probe_frames(mp4_path: Path) -> int:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_packets",
            "-show_entries",
            "stream=nb_read_packets",
            "-of",
            "csv=p=0",
            str(mp4_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return int(proc.stdout.strip() or 0)


async def _render_bookend(
    bookend: LongFormBookend,
    *,
    opening: bool,
    label: str,
    roster: list[RosterEntry],
    totals: list[tuple[int, int]],
    client: SatoriClient,
    episode_dir: Path,
    cache_dir: Path,
    fps: int,
    narrator: EpisodeNarrator | None,
    voice: str | None,
) -> dict[str, Any]:
    narration = await narrator.generate_text(bookend.script, voice) if narrator else None
    if narration is not None:
        # Same bounded pace fit as chapters (<=1.5x, pitch-preserving); anything
        # that still does not fit is rejected by bookend_duration, not cut off.
        narration = fit_narration_audio(narration, target_duration_s=MAX_BOOKEND_NARRATION_S)
    duration_s = bookend_duration(bookend, narration.duration_s if narration else None, fps)
    words = narration.word_timings if narration else []
    frames_dir = episode_dir / label / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for stale in frames_dir.glob("*.png"):
        stale.unlink()

    frame_total = round(duration_s * fps)
    for index in range(frame_total):
        props = sample_bookend_frame(
            bookend, index / fps, opening=opening, roster=roster, totals=totals, words=words
        )
        key = hashlib.sha256(
            (_renderer_digest() + "title" + json.dumps(props, sort_keys=True)).encode()
        ).hexdigest()
        cached = cache_dir / f"{key}.png"
        if cached.exists():
            png = cached.read_bytes()
        else:
            png = await client.render("title", props)
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(png)
        (frames_dir / f"frame_{index:04d}.png").write_bytes(png)

    mp4_path = episode_dir / f"{label}.mp4"
    cmd = build_ffmpeg_cmd(
        frames_dir=frames_dir,
        out_path=mp4_path,
        fps=fps,
        total_duration=duration_s,
        narration_path=narration.audio_path if narration else None,
    )
    await asyncio.to_thread(run_ffmpeg, cmd)
    return {
        "segment": label,
        "mp4": mp4_path,
        "frames": frame_total,
        "duration_s": duration_s,
        "frames_dir": frames_dir,
        "script": bookend.script,
        "word_timings": [w.model_dump() for w in words],
    }


def _write_chapter_batch(spec: LongFormSpec, chapters: list[StorySpec], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "id": story.id,
            "name": story.name,
            "sex": story.sex,
            "story": str(Path(ref).resolve()),
        }
        for story, ref in zip(chapters, spec.chapters, strict=True)
    ]
    with path.open("w") as fh:
        YAML().dump({"batch": f"{spec.id}-chapters", "videos": entries}, fh)


async def render_longform(
    spec_path: Path,
    satori_url: str,
    out_dir: Path,
    *,
    preview: bool = False,
    narrator: EpisodeNarrator | None = None,
) -> dict[str, Any]:
    """Render and assemble one episode; ``preview`` permits a draft but never releases."""
    spec = load_longform(spec_path)
    evaluation = evaluate_longform(spec, require_approval=not preview)
    if not evaluation.publishable:
        raise StoryQualityError("; ".join(evaluation.blockers))
    chapters = evaluation.chapters
    snapshots = [verified_snapshot(story) for story in chapters]
    roster = [roster_entry(story, snap) for story, snap in zip(chapters, snapshots, strict=True)]
    # The gate has already matched these to aggregate_claims; draw the recomputed values.
    totals = [(c.year, aggregate_total(snapshots, c.year)) for c in spec.aggregate_claims]

    started = time.monotonic()
    episode_dir = out_dir / spec.id
    chapters_dir = episode_dir / "chapters"
    batch_path = episode_dir / "chapters.yaml"
    _write_chapter_batch(spec, chapters, batch_path)
    specs = await load_specs(batch_path)
    total = len(specs)

    lexicon = Lexicon.from_yaml(_CAPTIONS_YAML)
    state = CombinationState(_STATE_DB)
    # Caption rule: every released video carries a hashtag set no other video used.
    # Case-folded to match the lowercase caption lexicon's recorded combinations.
    episode_tags = sorted(tag.lstrip("#").lower() for tag in spec.hashtags)
    episode_combo = combo_hash(episode_tags)
    if not preview and state.is_used(episode_combo):
        raise StoryQualityError(f"{spec.id}: hashtag combination already used by another video")
    segments: list[dict[str, Any]] = []
    async with SatoriClient(satori_url) as client:
        cache_dir = out_dir / ".cache"
        segments.append(
            await _render_bookend(
                spec.intro,
                opening=True,
                label="intro",
                roster=roster,
                totals=totals,
                client=client,
                episode_dir=episode_dir,
                cache_dir=cache_dir,
                fps=specs[0].fps,
                narrator=narrator,
                voice=spec.voice,
            )
        )
        for number, video in enumerate(specs, start=1):
            chapter = video.model_copy(
                update={
                    "id": f"{spec.id}-part{number}-{video.id}",
                    "chapter_label": f"PART {number} OF {total}",
                }
            )
            result = await render_spec(
                chapter,
                client,
                chapters_dir,
                lexicon,
                state,
                narration_provider=ChapterNarrator(narrator) if narrator else None,
            )
            qc = run_all_checks(result, chapters_dir)
            # A narration-free preview cannot satisfy the narration checks; it is
            # marked non-releasable in the manifest instead of failing here.
            waived = _NARRATION_CODES if narrator is None else frozenset()
            errors = [
                f"{i.code}: {i.message}"
                for i in qc.issues
                if i.severity == "error" and i.code not in waived
            ]
            if errors:
                raise StoryQualityError(f"{chapter.id} failed QC: {'; '.join(errors)}")
            segments.append(
                {
                    "segment": chapter.id,
                    "story_id": video.id,
                    "mp4": Path(str(result["mp4"])),
                    "frames": int(str(result["frames"])),
                    "duration_s": float(str(result["duration_s"])),
                }
            )
            console.print(f"[green]✓[/green] {chapter.id}")
        segments.append(
            await _render_bookend(
                spec.outro,
                opening=False,
                label="outro",
                roster=roster,
                totals=totals,
                client=client,
                episode_dir=episode_dir,
                cache_dir=cache_dir,
                fps=specs[0].fps,
                narrator=narrator,
                voice=spec.voice,
            )
        )
        satori_version = await client.get_version()

    fps = specs[0].fps
    expected_frames = sum(int(s["frames"]) for s in segments)
    expected_duration = round(expected_frames / fps, 3)
    if not MIN_EPISODE_S <= expected_duration <= MAX_EPISODE_S:
        raise StoryQualityError(
            f"{spec.id}: episode runs {expected_duration:.2f}s; "
            f"expected {MIN_EPISODE_S:.0f}-{MAX_EPISODE_S:.0f}s"
        )

    master = out_dir / f"{spec.id}.mp4"
    narrated = narrator is not None
    cmd = build_concat_cmd(
        [Path(s["mp4"]) for s in segments],
        [float(s["duration_s"]) for s in segments],
        master,
        fps,
        narrated,
    )
    await asyncio.to_thread(run_ffmpeg, cmd)

    qc = run_longform_checks(
        spec.id,
        master,
        Path(segments[0]["frames_dir"]),
        expected_frames,
        expected_duration,
        narrated,
        MIN_EPISODE_S,
        MAX_EPISODE_S,
    )
    measured_frames = _probe_frames(master)
    caption = f"{spec.social_caption.rstrip()} {' '.join(spec.hashtags)}"
    manifest = {
        "episode_id": spec.id,
        "title": spec.title,
        "preview": preview,
        "releasable": not preview and narrated and qc.passed,
        "approved_by": spec.approved_by,
        "approved_content_sha256": spec.approved_content_sha256,
        "duration_s": expected_duration,
        "frame_count": expected_frames,
        "measured_frame_count": measured_frames,
        "fps": fps,
        "output_path": str(master),
        "sha256": sha256_bytes(master.read_bytes()),
        "caption": caption,
        "pinned_comment": spec.share_prompt,
        "ai_voice_disclosure": "AI-generated narration" if narrated else None,
        "roster": [
            {
                "name": r.name,
                "peak_year": r.peak_year,
                "peak_count": r.peak_count,
                "latest_year": r.latest_year,
                "latest_count": r.latest_count,
                "decline_pct": r.decline_pct,
            }
            for r in roster
        ],
        "segments": [
            {k: (str(v) if isinstance(v, Path) else v) for k, v in s.items()} for s in segments
        ],
        "satori_version": satori_version,
        "ffmpeg_version": get_ffmpeg_version(),
        "render_time_s": round(time.monotonic() - started, 1),
        "qc": {
            "passed": qc.passed,
            "issues": [
                {"severity": i.severity, "code": i.code, "message": i.message} for i in qc.issues
            ],
        },
    }
    (out_dir / f"{spec.id}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if manifest["releasable"]:
        state.record(episode_combo, episode_tags, spec.id)
    if not qc.passed:
        errors = [f"{i.code}: {i.message}" for i in qc.issues if i.severity == "error"]
        raise StoryQualityError(f"{spec.id} failed episode QC: {'; '.join(errors)}")
    return manifest
