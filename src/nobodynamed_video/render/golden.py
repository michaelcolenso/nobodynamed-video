"""Golden frame hashing with explicit update semantics."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)

GOLDEN_DIR = Path("fixtures/golden")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def golden_path(spec_id: str, label: str) -> Path:
    """Return path like fixtures/golden/bertha-2024/hook_f00.sha256."""
    return GOLDEN_DIR / spec_id / f"{label}.sha256"


def check_or_write_golden(
    spec_id: str,
    label: str,
    png_bytes: bytes,
    *,
    update: bool = False,
) -> None:
    """Compare a hash, writing only during an explicit golden update."""
    actual = sha256_bytes(png_bytes)
    gp = golden_path(spec_id, label)

    if update:
        gp.parent.mkdir(parents=True, exist_ok=True)
        gp.write_text(actual + "\n")
        log.info("Golden written: %s  (%s)", gp, actual[:12])
        return
    if not gp.exists():
        raise AssertionError(
            f"Missing golden for {spec_id}/{label}: {gp}. "
            "Run the explicit `nbn goldens update` workflow after reviewing frames."
        )

    expected = gp.read_text().strip()
    if actual != expected:
        raise AssertionError(
            f"Golden frame mismatch for {spec_id}/{label}!\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual}\n"
            f"  golden file: {gp}\n"
            "If this change is intentional, delete the .sha256 file and re-render."
        )
    log.debug("Golden OK: %s", label)
