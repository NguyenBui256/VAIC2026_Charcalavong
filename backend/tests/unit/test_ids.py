"""Unit tests for UUID v7 generation — `app.core.ids.uuid7`."""

from __future__ import annotations

import time
import uuid

from app.core.ids import uuid7


def test_uuid7_returns_uuid_instance() -> None:
    """uuid7() returns a uuid.UUID object."""
    result = uuid7()
    assert isinstance(result, uuid.UUID)


def test_uuid7_sets_version_nibble_to_7() -> None:
    """The version nibble (top of byte 6) is 0x7."""
    result = uuid7()
    assert result.version == 7


def test_uuid7_sets_variant_bits() -> None:
    """The variant (top bits of byte 8) is 0b10 (RFC 4122 layout)."""
    result = uuid7()
    # Bytes layout: variant is in the first two bits of byte 8.
    bytes_ = result.bytes
    # The variant nibble is the top byte of clock_seq_hi_res...
    # For variant 10, the top two bits of byte 8 are 0b10.
    assert (bytes_[8] & 0b11000000) == 0b10000000


def test_uuid7_is_time_ordered_across_milliseconds() -> None:
    """Two uuid7 calls 10ms apart yield msb-increasing integers."""
    earlier = uuid7(timestamp_ms=1_700_000_000_000)
    later = uuid7(timestamp_ms=1_700_000_000_010)
    assert earlier.int < later.int


def test_uuid7_within_same_ms_preserves_sort_via_random() -> None:
    """Within the same ms, the integer values are random (no exact monotonicity
    guarantee), but the version nibble is still 7 for both."""
    a = uuid7(timestamp_ms=1_700_000_000_000)
    b = uuid7(timestamp_ms=1_700_000_000_000)
    assert a.version == 7 and b.version == 7
    # High likelihood they differ; assert to catch a stub.
    assert a != b


def test_uuid7_rejects_out_of_range_timestamps() -> None:
    """timestamp_ms must fit in 48 bits — negative or oversized values raise."""
    import pytest

    with pytest.raises(ValueError):
        uuid7(timestamp_ms=-1)
    with pytest.raises(ValueError):
        uuid7(timestamp_ms=1 << 48)


def test_uuid7_default_timestamp_close_to_now() -> None:
    """Default timestamp_ms is current time — encoded value is within 2 seconds."""
    before_ms = int(time.time() * 1000)
    result = uuid7()
    after_ms = int(time.time() * 1000)
    # Top 48 bits encode the timestamp.
    encoded_ms = result.int >> 80
    assert before_ms - 1 <= encoded_ms <= after_ms + 1
