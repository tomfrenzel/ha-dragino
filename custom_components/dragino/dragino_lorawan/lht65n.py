"""Dragino LHT65N LoRaWAN temperature and humidity sensor."""

from typing import Any, ClassVar

from ._decode import DecodeError, require_length, s16, u16, u24, u32
from .device import (
    CHIRPSTACK_BRAND_ID,
    STATUS_PORT,
    TTS_BRAND_ID,
    DraginoDevice,
    decode_status,
)

DATA_PORT = 2

# The poll flag marks the answer to a poll request and the retransmission flag
# marks stored data; both carry history rather than the current measurement.
HISTORY_FLAGS = 0xC0

EXT_NONE = 0
EXT_DS18B20 = 1
EXT_TMP117 = 2
EXT_INTERRUPT = 4
EXT_ILLUMINANCE = 5
EXT_ADC = 6
EXT_COUNT_16 = 7
EXT_COUNT_32 = 8
EXT_DS18B20_TIMESTAMP = 9
EXT_SHT31 = 11
EXT_PIR = 14
EXT_DS18B20_ID = 15

# 0x7FFF centi-degrees is what the probe input reports without a probe.
NO_PROBE = 327.67

_EXTERNAL_FIELDS = (
    "external_sensor",
    "external_temperature",
    "external_humidity",
    "illuminance",
    "adc_voltage",
    "count",
    "interrupt_level",
    "pir_activity",
)


def _probe_temperature(data: bytes, index: int) -> float | None:
    temperature = s16(data, index) / 100
    return None if temperature >= NO_PROBE else temperature


def _humidity(data: bytes, index: int) -> float:
    return (u16(data, index) & 0x0FFF) / 10


class Lht65n(DraginoDevice):
    """Temperature and humidity sensor with an optional external probe."""

    MODEL = "LHT65N"
    NAMES = ("LHT65N",)
    identifiers: ClassVar = {
        "chirpstack": (CHIRPSTACK_BRAND_ID, "f60ee224-4023-4574-8bcc-45e237c4c02b"),
        "tts": (TTS_BRAND_ID, "lht65n"),
    }

    temperature: float | None = None
    humidity: float | None = None
    external_sensor: int | None = None
    external_temperature: float | None = None
    external_humidity: float | None = None
    illuminance: int | None = None
    adc_voltage: float | None = None
    count: int | None = None
    interrupt_level: bool | None = None
    pir_activity: bool | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> dict[str, Any]:
        """Decode live measurement uplinks on fPort 2 and the status on fPort 5."""
        if f_port == STATUS_PORT:
            return decode_status(data)
        if f_port != DATA_PORT:
            return {}
        require_length(data, 11, 15)
        if data[6] & HISTORY_FLAGS:
            return {}
        external = data[6] & 0x0F
        if external == EXT_INTERRUPT and len(data) != 15:
            raise DecodeError("Interrupt payloads must be 15 bytes")

        values: dict[str, Any] = dict.fromkeys(_EXTERNAL_FIELDS)
        values["external_sensor"] = external
        if external != EXT_DS18B20_TIMESTAMP:
            values["battery_voltage"] = (u16(data, 0) & 0x3FFF) / 1000
        if external != EXT_DS18B20_ID:
            values["temperature"] = s16(data, 2) / 100
            values["humidity"] = _humidity(data, 4)

        if external in (EXT_DS18B20, EXT_TMP117):
            values["external_temperature"] = _probe_temperature(data, 7)
        elif external == EXT_DS18B20_TIMESTAMP:
            values["external_temperature"] = _probe_temperature(data, 0)
        elif external == EXT_INTERRUPT:
            values["interrupt_level"] = bool(data[7])
            values["count"] = u24(data, 9)
        elif external == EXT_ILLUMINANCE:
            values["illuminance"] = u16(data, 7)
        elif external == EXT_ADC:
            values["adc_voltage"] = u16(data, 7) / 1000
        elif external == EXT_COUNT_16:
            values["count"] = u16(data, 7)
        elif external == EXT_COUNT_32:
            values["count"] = u32(data, 7)
        elif external == EXT_SHT31:
            temperature = _probe_temperature(data, 7)
            values["external_temperature"] = temperature
            values["external_humidity"] = None if temperature is None else _humidity(data, 9)
        elif external == EXT_PIR:
            values["pir_activity"] = bool(data[7] & 0x01)
            values["count"] = u24(data, 8)
        return values
