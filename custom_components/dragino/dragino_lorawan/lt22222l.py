"""Dragino LT-22222-L LoRaWAN I/O controller."""

from typing import Any, ClassVar

from ._decode import firmware_version, require_length, s16, u16, u32
from .device import CHIRPSTACK_BRAND_ID, TTS_BRAND_ID, DraginoDevice

DATA_PORT = 2
STATUS_PORT = 5

MODE_2ACI_2AVI = 1
MODE_COUNT_1 = 2
MODE_2ACI_1COUNT = 3
MODE_COUNT_2 = 4
MODE_1ACI_2AVI_1COUNT = 5
MODE_TRIGGER = 6

WORK_MODES = {
    MODE_2ACI_2AVI: "2aci_2avi",
    MODE_COUNT_1: "count_1",
    MODE_2ACI_1COUNT: "2aci_1count",
    MODE_COUNT_2: "count_2",
    MODE_1ACI_2AVI_1COUNT: "1aci_2avi_1count",
    MODE_TRIGGER: "trigger",
}

_MODE_FIELDS = (
    "work_mode",
    "avi1",
    "avi2",
    "aci1",
    "aci2",
    "count1",
    "count2",
    "di1",
    "di2",
    "do1",
    "do2",
    "ro1",
    "ro2",
)


class Lt22222l(DraginoDevice):
    """Two digital inputs and outputs, two relays and two analog inputs of each kind."""

    MODEL = "LT-22222-L"
    NAMES = ("LT-22222-L",)
    identifiers: ClassVar = {
        "chirpstack": (CHIRPSTACK_BRAND_ID, "cb0a7bef-eaa0-4c61-a0b6-ce33e6ecbc4f"),
        "tts": (TTS_BRAND_ID, "lt22222-l"),
    }

    work_mode: str | None = None
    avi1: float | None = None
    avi2: float | None = None
    aci1: float | None = None
    aci2: float | None = None
    count1: int | None = None
    count2: int | None = None
    di1: bool | None = None
    di2: bool | None = None
    do1: bool | None = None
    do2: bool | None = None
    ro1: bool | None = None
    ro2: bool | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> dict[str, Any]:
        """Decode the 11-byte uplink on fPort 2 and the settings on fPort 5.

        Voltages are in V and currents in mA. Outputs and relays are on when their
        status bit is set; Dragino's own decoder labels a set DO bit as level "L".
        """
        if f_port == STATUS_PORT:
            require_length(data, 7)
            return {"firmware_version": firmware_version(data[2], data[3])}
        if f_port != DATA_PORT:
            return {}
        require_length(data, 11)
        mode = data[10] & 0x3F
        status = data[8]
        values: dict[str, Any] = dict.fromkeys(_MODE_FIELDS)
        values["work_mode"] = WORK_MODES.get(mode)

        if mode == MODE_TRIGGER:
            values["di1"] = bool(data[2] & 0x02)
            values["di2"] = bool(data[2] & 0x08)
            return values

        values["do1"] = bool(status & 0x01)
        values["do2"] = bool(status & 0x02)
        values["ro1"] = bool(status & 0x80)
        values["ro2"] = bool(status & 0x40)
        if mode not in (MODE_2ACI_2AVI, MODE_1ACI_2AVI_1COUNT):
            values["count1"] = u32(data, 0)

        if mode == MODE_2ACI_2AVI:
            values.update(
                avi1=s16(data, 0) / 1000,
                avi2=s16(data, 2) / 1000,
                aci1=s16(data, 4) / 1000,
                aci2=s16(data, 6) / 1000,
                di1=bool(status & 0x08),
                di2=bool(status & 0x10),
            )
        elif mode == MODE_COUNT_1:
            values["count2"] = u32(data, 4)
        elif mode == MODE_2ACI_1COUNT:
            values.update(aci1=s16(data, 4) / 1000, aci2=s16(data, 6) / 1000)
        elif mode == MODE_1ACI_2AVI_1COUNT:
            values.update(
                avi1=s16(data, 0) / 1000,
                avi2=s16(data, 2) / 1000,
                aci1=s16(data, 4) / 1000,
                count1=u16(data, 6),
            )
        return values
