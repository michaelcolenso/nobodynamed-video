"""Golden frame hashing — SHA-256 of PNG bytes for regression detection.

On first run (no golden file): writes the hash and passes.
On subsequent runs: compares against stored hash; fails loudly on mismatch.
"""

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


def check_or_write_golden(spec_id: str, label: str, png_bytes: bytes) -> None:
    """Compare PNG hash to the stored golden, or write it if missing.

    Raises AssertionError if the hash does not match the stored golden.
    """
    actual = sha256_bytes(png_bytes)
    gp = golden_path(spec_id, label)

    if not gp.exists():
        gp.parent.mkdir(parents=True, exist_ok=True)
        gp.write_text(actual + "\n")
        log.info("Golden written: %s  (%s)", gp, actual[:12])
        return

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
