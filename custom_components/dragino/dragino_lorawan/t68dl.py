"""Dragino T68DL LoRaWAN temperature sensor with data logger."""

from typing import Any, ClassVar

from ._decode import require_length, s16, u16
from .device import (
    CHIRPSTACK_BRAND_ID,
    STATUS_PORT,
    DraginoDevice,
    decode_status,
)

DATA_PORT = 2


class T68dl(DraginoDevice):
    """Temperature probe with configurable high and low alarm thresholds."""

    MODEL = "T68DL"
    NAMES = ("T68DL",)
    # The model is only part of the ChirpStack catalog, not of the TTN repository.
    identifiers: ClassVar = {
        "chirpstack": (CHIRPSTACK_BRAND_ID, "818138c6-9e6a-4562-a997-97a4e5110e0e"),
    }

    temperature: float | None = None
    temperature_high: bool | None = None
    temperature_low: bool | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> dict[str, Any]:
        """Decode the 9-byte measurement uplink on fPort 2 and the status on fPort 5."""
        if f_port == STATUS_PORT:
            return decode_status(data)
        if f_port != DATA_PORT:
            return {}
        require_length(data, 9)
        return {
            "battery_voltage": u16(data, 0) / 1000,
            "temperature": s16(data, 2) / 100,
            "temperature_high": bool(data[4] & 0x01),
            "temperature_low": bool(data[4] & 0x02),
        }
