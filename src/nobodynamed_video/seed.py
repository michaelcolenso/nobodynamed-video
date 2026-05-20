"""Deterministic seed helpers: name + year → int64."""

import hashlib


def name_seed(name: str, year: int) -> int:
    """Return a deterministic int64 seed derived from name and year.

    Uses BLAKE2b (32-byte digest) so the same name+year always produces the
    same seed, regardless of Python hash randomisation.
    """
    key = f"{name}|{year}".encode()
    digest = hashlib.blake2b(key, digest_size=8).digest()
    # Interpret as unsigned 64-bit big-endian, then mask to signed int64 range.
    value = int.from_bytes(digest, byteorder="big")
    # Clip to int64 range so it's safe to pass to random.seed() or numpy.
    return value & 0x7FFF_FFFF_FFFF_FFFF


def spec_seed(spec_id: str) -> int:
    """Return a deterministic seed for a full VideoSpec id (e.g. 'bertha-2024')."""
    # Split on last '-' to extract name and year components.
    parts = spec_id.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return name_seed(parts[0], int(parts[1]))
    # Fall back to hashing the whole id string.
    digest = hashlib.blake2b(spec_id.encode(), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big") & 0x7FFF_FFFF_FFFF_FFFF
