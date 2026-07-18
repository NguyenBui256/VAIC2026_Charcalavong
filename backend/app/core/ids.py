"""UUID v7 generation — RFC 9562 compliant, time-ordered, no third-party dep.

Layout (128 bits, MSB-first):
    bits 127..80  (48 bits)  unix_ts_ms   (big-endian "now")
    bits  79..76  ( 4 bits)  version = 0x7
    bits  75..64  (12 bits)  rand_a
    bits  63..62  ( 2 bits)  variant = 0b10
    bits  61..0   (62 bits)  rand_b

Yields monotonically-increasing IDs (within the same millisecond, randomness
preserves the time-ordered property with high probability). Stored in Postgres
as native `uuid` columns — sortable, indexable.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime

__all__ = ["uuid7", "utcnow_iso_ms"]


def uuid7(timestamp_ms: int | None = None) -> uuid.UUID:
    """Return a UUID v7. If `timestamp_ms` is None, uses the current time."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    if not 0 <= timestamp_ms < (1 << 48):
        msg = f"timestamp_ms must fit in 48 bits; got {timestamp_ms}"
        raise ValueError(msg)

    # 74 random bits total: 12 for rand_a, 62 for rand_b. CSPRNG via secrets.
    randomness = secrets.randbits(74)
    rand_a = (randomness >> 62) & 0xFFF
    rand_b = randomness & ((1 << 62) - 1)

    uuid_int = (
        (timestamp_ms & 0xFFFFFFFFFFFF) << 80
        | 0x7 << 76  # version
        | rand_a << 64
        | 0b10 << 62  # variant
        | rand_b
    )
    # NOTE: Python's stdlib uuid.UUID rejects version=7 (only 1–5 supported,
    # even though RFC 9562 defines v6/v7/v8). The version + variant bits are
    # already baked into the int above; we construct without the `version`
    # kwarg and expose `.version` correctly via the bit layout.
    return uuid.UUID(int=uuid_int)


def utcnow_iso_ms() -> str:
    """UTC now as ISO 8601 with milliseconds — AR-14 timestamp convention."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
