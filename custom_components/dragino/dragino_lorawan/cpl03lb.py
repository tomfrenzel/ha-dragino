"""Dragino CPL03-LB LoRaWAN outdoor pulse contact sensor."""

from typing import Any, ClassVar

from ._decode import DecodeError, require_length, u24
from .device import (
    CHIRPSTACK_BRAND_ID,
    STATUS_PORT,
    TTS_BRAND_ID,
    DraginoDevice,
    decode_status,
)

DATA_PORT = 2
PULSE_PORT = 6
CONTACT_STATUS_PORT = 7
SENSOR_MODEL = 0x20
FREQUENCY_BANDS = range(0x01, 0x0F)
THREE_CONTACT_MODE = 0x08

_MODE_FIELDS = (
    "contact_open",
    "pulse_count",
    "last_duration",
    "alarm",
    "pa8_count",
    "pa4_count",
    "pb15_count",
)


class Cpl03Lb(DraginoDevice):
    """Dry contact sensor that counts pulses on one or three inputs."""

    MODEL = "CPL03-LB"
    NAMES = ("CPL03-LB",)
    identifiers: ClassVar = {
        "chirpstack": (CHIRPSTACK_BRAND_ID, "621f921e-4685-4421-b8a0-b4cc6b5d77b8"),
        "tts": (TTS_BRAND_ID, "cpl03-lb"),
    }

    work_mode: str | None = None
    contact_open: bool | None = None
    pulse_count: int | None = None
    last_duration: int | None = None
    alarm: bool | None = None
    pa8_count: int | None = None
    pa4_count: int | None = None
    pb15_count: int | None = None
    pa8_open: bool | None = None
    pa4_open: bool | None = None
    pb15_open: bool | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> dict[str, Any]:
        """Decode contacts on fPort 2/7, counters on fPort 6 and status on fPort 5.

        The duration is in seconds. Contact states on fPort 7 are reported as
        closed when the bit is set, the opposite of the single contact status
        bit on fPort 2.
        """
        if f_port == STATUS_PORT:
            status = decode_status(data)
            if data[0] != SENSOR_MODEL:
                raise DecodeError(f"Unexpected sensor model {data[0]:#04x}")
            if data[3] not in FREQUENCY_BANDS:
                raise DecodeError(f"Unknown frequency band {data[3]}")
            return status
        if f_port == CONTACT_STATUS_PORT:
            if not data:
                raise DecodeError("Empty contact status payload")
            return {
                "pa8_open": not (data[0] & 0x01),
                "pa4_open": not (data[0] & 0x04),
                "pb15_open": not (data[0] & 0x10),
            }
        if f_port not in (DATA_PORT, PULSE_PORT):
            return {}
        if f_port == PULSE_PORT:
            require_length(data, 10, 11)
        else:
            require_length(data, 11)
        three_contacts = bool(data[0] & THREE_CONTACT_MODE)
        if three_contacts != (f_port == PULSE_PORT):
            raise DecodeError(f"Unexpected work mode for fPort {f_port}")
        values: dict[str, Any] = dict.fromkeys(_MODE_FIELDS)
        if three_contacts:
            values["work_mode"] = "cpl03"
            values["pa8_count"] = u24(data, 1)
            values["pa4_count"] = u24(data, 4)
            values["pb15_count"] = u24(data, 7)
        else:
            values["work_mode"] = "cpl01"
            values["contact_open"] = bool(data[0] & 0x01)
            values["alarm"] = bool(data[0] & 0x02)
            values["pulse_count"] = u24(data, 1)
            values["last_duration"] = u24(data, 4)
        return values
