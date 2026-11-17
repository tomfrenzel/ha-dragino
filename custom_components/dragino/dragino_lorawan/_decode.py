"""Helpers shared by all Dragino payload decoders."""

from collections.abc import Sequence


class DecodeError(ValueError):
    """The payload does not match the layout of the device."""


def require_length(data: bytes, *lengths: int) -> None:
    """Reject payloads whose size is not one of the documented sizes."""
    if len(data) not in lengths:
        expected = " or ".join(str(length) for length in lengths)
        raise DecodeError(f"Expected {expected} bytes, got {len(data)}")


def u16(data: Sequence[int], index: int) -> int:
    """Read an unsigned big-endian 16-bit integer."""
    return data[index] << 8 | data[index + 1]


def s16(data: Sequence[int], index: int) -> int:
    """Read a signed big-endian 16-bit integer."""
    value = u16(data, index)
    return value - 0x10000 if value & 0x8000 else value


def u24(data: Sequence[int], index: int) -> int:
    """Read an unsigned big-endian 24-bit integer."""
    return data[index] << 16 | data[index + 1] << 8 | data[index + 2]


def u32(data: Sequence[int], index: int) -> int:
    """Read an unsigned big-endian 32-bit integer."""
    return data[index] << 24 | u24(data, index + 1)


def firmware_version(high: int, low: int) -> str:
    """Format the firmware version bytes of an fPort 5 status uplink."""
    return f"{high & 0x0F}.{(low >> 4) & 0x0F}.{low & 0x0F}"
