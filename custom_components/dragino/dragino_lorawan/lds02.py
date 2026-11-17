"""Dragino LDS02 door sensor and LWL02 water leak sensor."""

from typing import Any, ClassVar

from ._decode import require_length, u16, u24
from .device import CHIRPSTACK_BRAND_ID, TTS_BRAND_ID, DraginoDevice

DATA_PORT = 10

MODE_DOOR = 1
MODE_WATER_LEAK = 2
MODE_DOOR_AND_WATER_LEAK = 3


class _Contact(DraginoDevice):
    """The LDS02 and LWL02 share hardware and payload; the mode selects the data."""

    mode: int | None = None
    door_open: bool | None = None
    door_open_count: int | None = None
    last_door_open_duration: int | None = None
    water_leak: bool | None = None
    water_leak_count: int | None = None
    last_water_leak_duration: int | None = None
    alarm: bool | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> dict[str, Any]:
        """Decode the 10-byte uplink on fPort 10; durations are in minutes."""
        if f_port != DATA_PORT:
            return {}
        require_length(data, 10)
        mode = data[2]
        values: dict[str, Any] = {
            "battery_voltage": (u16(data, 0) & 0x3FFF) / 1000,
            "mode": mode,
            "door_open": None,
            "door_open_count": None,
            "last_door_open_duration": None,
            "water_leak": None,
            "water_leak_count": None,
            "last_water_leak_duration": None,
            "alarm": None,
        }
        if mode == MODE_DOOR:
            values["door_open"] = bool(data[0] & 0x80)
            values["door_open_count"] = u24(data, 3)
            values["last_door_open_duration"] = u24(data, 6)
            values["alarm"] = bool(data[9] & 0x01)
        elif mode == MODE_WATER_LEAK:
            values["water_leak"] = bool(data[0] & 0x40)
            values["water_leak_count"] = u24(data, 3)
            values["last_water_leak_duration"] = u24(data, 6)
        elif mode == MODE_DOOR_AND_WATER_LEAK:
            values["door_open"] = bool(data[0] & 0x80)
            values["water_leak"] = bool(data[0] & 0x40)
            values["alarm"] = bool(data[9] & 0x01)
        return values


class Lds02(_Contact):
    """Door sensor with a magnetic contact."""

    MODEL = "LDS02"
    NAMES = ("LDS02",)
    identifiers: ClassVar = {
        "chirpstack": (CHIRPSTACK_BRAND_ID, "55deef19-c13c-4b69-a10d-2e89f6398a02"),
        "tts": (TTS_BRAND_ID, "lds02"),
    }


class Lwl02(_Contact):
    """Water leak sensor with a leak probe."""

    MODEL = "LWL02"
    NAMES = ("LWL02",)
    identifiers: ClassVar = {
        "chirpstack": (CHIRPSTACK_BRAND_ID, "b9a99932-c5e0-40fb-a673-85c24640cf7c"),
        "tts": (TTS_BRAND_ID, "lwl02"),
    }
