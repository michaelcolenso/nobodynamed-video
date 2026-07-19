"""Narrative scene copy selection — variant library with deterministic pick."""

from __future__ import annotations

from pathlib import Path
from random import Random
from typing import Any, TypedDict, cast

from ruamel.yaml import YAML

from nobodynamed_video.data.claim_safety import copy_is_supported
from nobodynamed_video.data.hooks import passes_data_guards, render_hook_template
from nobodynamed_video.exceptions import HookResolutionError
from nobodynamed_video.models import ProgramType, Tier, VideoContext

NARRATIVES_PATH = Path("batches/narratives.yaml")

_NARRATIVE_SALT = 0x6E617272

_FALLBACK = (
    "The data speaks for itself.",
    None,
)


class NarrativeDef(TypedDict):
    id: str
    program: str
    compatible_tiers: list[str]
    requires_var: str | None
    requires_data: dict[str, dict[str, float]] | None
    primary: str
    supporting: str


def load_narrative_library(path: Path = NARRATIVES_PATH) -> dict[str, object]:
    yaml = YAML(typ="safe")
    raw = yaml.load(path.read_text())
    if not isinstance(raw, dict):
        raise HookResolutionError(f"Invalid narratives library at {path}")
    return raw


def _program_key(program: ProgramType) -> str:
    return program.value


def select_narrative(
    ctx: VideoContext,
    program: ProgramType,
    tier: Tier,
    seed: int,
    library: dict[str, object] | None = None,
) -> tuple[str, str | None]:
    """Pick a narrative variant deterministically. Returns (primary, supporting)."""
    lib = library or load_narrative_library()
    raw_narratives = lib.get("narratives", [])
    if not isinstance(raw_narratives, list):
        return _FALLBACK

    narratives = cast(list[NarrativeDef], raw_narratives)
    key = _program_key(program)

    candidates = [
        n
        for n in narratives
        if n.get("program") == key and tier.value in n.get("compatible_tiers", [])
    ]

    ctx_dict: dict[str, Any] = ctx.as_template_context()
    viable: list[NarrativeDef] = []
    for narr in candidates:
        required = narr.get("requires_var")
        if required and ctx_dict.get(required) is None:
            continue
        if not passes_data_guards(narr.get("requires_data"), ctx_dict):
            continue
        if not copy_is_supported(
            f"{narr.get('primary', '')} {narr.get('supporting', '')}", ctx_dict
        ):
            continue
        viable.append(narr)

    if not viable:
        return _FALLBACK

    salted_seed = seed ^ _NARRATIVE_SALT
    selected = viable[Random(salted_seed).randrange(len(viable))]

    primary = render_hook_template(str(selected["primary"]), ctx_dict)
    supporting_raw = render_hook_template(str(selected["supporting"]), ctx_dict)
    supporting = supporting_raw if supporting_raw else None

    return primary, supporting
