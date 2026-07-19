"""Fail-closed editorial checks for executable copy templates."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from nobodynamed_video.models import ObservationStatus

_UNSUPPORTED = (
    re.compile(r"\b(mean|average) age\b", re.IGNORECASE),
    re.compile(r"\bevery living\b", re.IGNORECASE),
    re.compile(r"\bmost\s+{{.*?}}s are over\b", re.IGNORECASE),
    re.compile(r"\b(one bad year from|heading to|from) zero\b", re.IGNORECASE),
    re.compile(r"\bextinct(ion)?\b", re.IGNORECASE),
    re.compile(r"\bevery\s+{{.*?}}\s+ever born\b", re.IGNORECASE),
)


def copy_is_supported(template: str, ctx: Mapping[str, Any]) -> bool:
    """Return whether a template's claims are supported by this context."""
    if any(pattern.search(template) for pattern in _UNSUPPORTED):
        return False
    current_status = ctx.get("current_status")
    status_value = (
        current_status.value
        if isinstance(current_status, ObservationStatus)
        else str(current_status)
    )
    observation_dependent_fields = (
        "{{ current_count",
        "{{ current_rank",
        "{{ decline_pct",
        "{{ rise_pct",
    )
    if status_value != ObservationStatus.OBSERVED.value and any(
        field in template for field in observation_dependent_fields
    ):
        return False
    if "{{ current_rank" in template and int(ctx.get("current_rank", 9999)) == 9999:
        return False
    if "{{ rank_at_peak" in template and int(ctx.get("rank_at_peak", 9999)) == 9999:
        return False
    if "{{ comparison_name" in template and not ctx.get("comparison_reason"):
        return False
    if "{{ killing_event" in template:
        event = ctx.get("cultural_event")
        if not isinstance(event, Mapping) or not event.get("validated"):
            return False
    return True
