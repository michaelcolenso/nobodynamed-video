"""Create burned-caption SRT from the same approved editorial copy."""

from __future__ import annotations

from pathlib import Path

from nobodynamed_video.models import VideoSpec


def _time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_srt(spec: VideoSpec, path: Path) -> Path:
    if spec.hook is None or spec.context is None:
        raise RuntimeError("Approved hook and context are required for captions")
    durations = {scene.kind: scene.duration_s for scene in spec.scenes}
    beats = [
        (0.0, durations["hook"], f"{spec.hook.headline}\n{spec.hook.subhead}"),
        (
            durations["hook"],
            durations["hook"] + durations["reveal"],
            f"Peak: {spec.context.peak_count:,} recorded births in {spec.context.peak_year}",
        ),
        (
            durations["hook"] + durations["reveal"],
            durations["hook"] + durations["reveal"] + durations["narrative"],
            "\n".join(
                text
                for text in (
                    spec.context.narrative_text,
                    spec.context.supporting_text,
                )
                if text
            ),
        ),
        (
            sum(durations[k] for k in ("hook", "reveal", "narrative")),
            sum(durations.values()),
            "Run your name at nobodynamed.com",
        ),
    ]
    blocks = [
        f"{index}\n{_time(start)} --> {_time(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(beats, start=1)
    ]
    path.write_text("\n".join(blocks))
    return path
