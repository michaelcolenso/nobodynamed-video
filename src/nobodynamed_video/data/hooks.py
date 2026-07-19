"""Editorial hook loading, rendering, and selection."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from random import Random
from typing import TypedDict, cast

from ruamel.yaml import YAML

from nobodynamed_video.data.claim_safety import copy_is_supported
from nobodynamed_video.exceptions import HookResolutionError
from nobodynamed_video.models import ProgramType, ResolvedHook, Tier, VideoContext

HOOKS_PATH = Path("batches/hooks.yaml")
_HOOK_EXPR = re.compile(r"{{\s*(.*?)\s*}}")
TemplateValue = str | int | float | Tier | None
NumericTemplateValue = str | int | float


class HookDef(TypedDict):
    id: str
    pillar: str
    register: str
    headline: str
    subhead: str
    pinned_comment: str
    caption: str
    compatible_tiers: list[str]
    requires_var: str | None
    requires_data: dict[str, dict[str, float]] | None


def _thousands(value: TemplateValue) -> str:
    return f"{int(cast(NumericTemplateValue, value)):,}"


def _tier_label(value: TemplateValue) -> str:
    if isinstance(value, Tier):
        return value.value.upper()
    return str(value).upper()


def _ordinal(value: TemplateValue) -> str:
    number = int(cast(NumericTemplateValue, value))
    if 10 <= (number % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _decade_label(value: TemplateValue) -> str:
    return f"the {int(cast(NumericTemplateValue, value))}s"


def _years_word(value: TemplateValue) -> str:
    return "year" if int(cast(NumericTemplateValue, value)) == 1 else "years"


FILTERS: dict[str, Callable[[TemplateValue], str]] = {
    "thousands": _thousands,
    "tier_label": _tier_label,
    "ordinal": _ordinal,
    "decade_label": _decade_label,
    "years_word": _years_word,
}


def passes_data_guards(requires_data: object, ctx: Mapping[str, TemplateValue]) -> bool:
    """Evaluate numeric guard bounds like ``{decline_pct: {max: 30}}`` against ctx.

    Tier membership alone guarantees very little about a name's history (STABLE
    is the classifier's default bucket), so copy that makes a quantitative claim
    declares the bounds under which the claim is true. A guard passes only when
    the context value is a real number inside every declared bound; None fails
    closed so copy never attaches to a name whose data cannot prove its claim.
    """
    if requires_data is None:
        return True
    if not isinstance(requires_data, Mapping):
        raise HookResolutionError(f"requires_data must be a mapping: {requires_data!r}")
    for var_name, bounds in requires_data.items():
        if not isinstance(bounds, Mapping):
            raise HookResolutionError(
                f"requires_data[{var_name!r}] must be a mapping of min/max bounds"
            )
        value = ctx.get(str(var_name))
        if isinstance(value, bool) or not isinstance(value, int | float):
            return False
        for bound_name, bound in bounds.items():
            if isinstance(bound, bool) or not isinstance(bound, int | float):
                raise HookResolutionError(
                    f"requires_data[{var_name!r}].{bound_name} must be a number"
                )
            if bound_name == "min":
                if value < bound:
                    return False
            elif bound_name == "max":
                if value > bound:
                    return False
            else:
                raise HookResolutionError(
                    f"Unknown bound {bound_name!r} in requires_data[{var_name!r}]" " (use min/max)"
                )
    return True


def load_hook_library(path: Path = HOOKS_PATH) -> dict[str, object]:
    yaml = YAML(typ="safe")
    raw = yaml.load(path.read_text())
    if not isinstance(raw, dict):
        raise HookResolutionError(f"Invalid hooks library at {path}")
    hooks = raw.get("hooks")
    if not isinstance(hooks, list):
        raise HookResolutionError("Hooks library must contain a list under 'hooks'")
    required = {
        "id",
        "pillar",
        "register",
        "compatible_tiers",
        "headline",
        "subhead",
        "pinned_comment",
        "caption",
    }
    seen: set[str] = set()
    for hook in hooks:
        if not isinstance(hook, dict):
            raise HookResolutionError(f"Hook must be a mapping: {hook!r}")
        missing = required - set(hook)
        if missing:
            raise HookResolutionError(f"Hook missing {sorted(missing)}: {hook!r}")
        hook_id = str(hook["id"])
        if hook_id in seen:
            raise HookResolutionError(f"Duplicate hook id: {hook_id}")
        seen.add(hook_id)
    return raw


def render_hook_template(template: str, ctx: Mapping[str, TemplateValue]) -> str:
    def _replace(match: re.Match[str]) -> str:
        expr = match.group(1)
        parts = [part.strip() for part in expr.split("|")]
        value = ctx.get(parts[0])
        for filter_name in parts[1:]:
            filter_fn = FILTERS.get(filter_name)
            if filter_fn is None:
                raise HookResolutionError(f"Unknown hook filter: {filter_name}")
            value = filter_fn(value)
        return "" if value is None else str(value)

    return _HOOK_EXPR.sub(_replace, template).strip()


def pillar_to_program(pillar: str) -> ProgramType:
    if pillar == "resurrection":
        return ProgramType.RETURN_NOTICE
    if pillar == "cultural-collapse":
        return ProgramType.CULTURAL_EVENT
    return ProgramType.CASE_FILE


def style_to_pillar(style: str | None, tier: Tier, has_event: bool) -> str:
    if style == "cultural-collapse" and has_event:
        return "cultural-collapse"
    if style == "rising":
        return "resurrection"
    if style == "stable":
        return "peak-year"
    if style == "declining":
        return "extinction-watch"
    if tier in (Tier.RISING, Tier.RESURRECTED):
        return "resurrection"
    if style == "peak-year":
        return "peak-year"
    if style == "generation-arc":
        return "generation-arc"
    if style == "comparison-surprise":
        return "comparison-surprise"
    return "extinction-watch"


def resolve_hook(
    ctx: VideoContext,
    style: str | None,
    spec_seed: int,
    hook_id: str | None = None,
    library: dict[str, object] | None = None,
) -> ResolvedHook:
    lib = library or load_hook_library()
    raw_hooks = lib.get("hooks", [])
    if not isinstance(raw_hooks, list):
        raise HookResolutionError("Hooks library must contain a list under 'hooks'")
    hooks = cast(list[HookDef], raw_hooks)
    if hook_id:
        candidates = [hook for hook in hooks if hook.get("id") == hook_id]
        if not candidates:
            raise HookResolutionError(f"Unknown hook id: {hook_id}")
    else:
        target_pillar = style_to_pillar(style, ctx.tier, ctx.killing_event is not None)
        candidates = [
            hook
            for hook in hooks
            if (
                hook.get("pillar") == target_pillar
                and ctx.tier.value in hook.get("compatible_tiers", [])
            )
        ]
        if not candidates and target_pillar != "peak-year":
            candidates = [
                hook
                for hook in hooks
                if hook.get("pillar") == "peak-year"
                and ctx.tier.value in hook.get("compatible_tiers", [])
            ]

    viable: list[HookDef] = []
    ctx_dict = ctx.as_template_context()
    for hook in candidates:
        required = hook.get("requires_var")
        if required and ctx_dict.get(required) is None:
            continue
        if not passes_data_guards(hook.get("requires_data"), ctx_dict):
            continue
        copy = " ".join(
            str(hook.get(field, ""))
            for field in ("headline", "subhead", "pinned_comment", "caption")
        )
        if not copy_is_supported(copy, ctx_dict):
            continue
        viable.append(hook)

    if not viable:
        raise HookResolutionError(
            f"No compatible hook for name={ctx.name!r}, tier={ctx.tier.value}, style={style!r}"
        )

    selected = viable[Random(spec_seed).randrange(len(viable))]
    return ResolvedHook(
        id=str(selected["id"]),
        pillar=str(selected["pillar"]),
        voice_register=str(selected["register"]),
        headline=render_hook_template(str(selected["headline"]), ctx_dict),
        subhead=render_hook_template(str(selected["subhead"]), ctx_dict),
        pinned_comment=render_hook_template(str(selected["pinned_comment"]), ctx_dict),
        caption=render_hook_template(str(selected["caption"]), ctx_dict),
        requires_var=str(selected["requires_var"]) if selected.get("requires_var") else None,
    )
