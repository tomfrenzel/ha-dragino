"""Dragino LDDS75 LoRaWAN distance detection sensor."""

from typing import Any, ClassVar

from ._decode import require_length, s16, u16
from .device import CHIRPSTACK_BRAND_ID, TTS_BRAND_ID, DraginoDevice

DATA_PORT = 2
NO_SENSOR = 0
INVALID_READING = 20


class Ldds75(DraginoDevice):
    """Ultrasonic distance sensor with an internal temperature sensor."""

    MODEL = "LDDS75"
    NAMES = ("LDDS75",)
    identifiers: ClassVar = {
        "chirpstack": (CHIRPSTACK_BRAND_ID, "eaaf6138-870f-48d3-b0ec-299350cb88af"),
        "tts": (TTS_BRAND_ID, "ldds75"),
    }

    distance: int | None = None
    temperature: float | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> dict[str, Any]:
        """Decode the 8-byte measurement uplink on fPort 2."""
        if f_port != DATA_PORT:
            return {}
        require_length(data, 8)
        distance = u16(data, 2)
        return {
            "battery_voltage": (u16(data, 0) & 0x3FFF) / 1000,
            "distance": None if distance in (NO_SENSOR, INVALID_READING) else distance,
            "temperature": s16(data, 5) / 10,
        }
