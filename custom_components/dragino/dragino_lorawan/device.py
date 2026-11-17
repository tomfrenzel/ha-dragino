"""Base class for Dragino LoRaWAN devices."""

from collections.abc import Mapping, Sequence
from datetime import datetime
import logging
from typing import Any, ClassVar

from lorawan_connection import (
    Device,
    DeviceDescriptor,
    DeviceEvent,
    GatewayReception,
    UplinkEvent,
)

from ._decode import DecodeError, firmware_version, require_length, u16

_LOGGER = logging.getLogger(__name__)

CHIRPSTACK_BRAND_ID = 676
TTS_BRAND_ID = "dragino"
BRAND_IDS: Mapping[str, int | str] = {
    "chirpstack": CHIRPSTACK_BRAND_ID,
    "tts": TTS_BRAND_ID,
}

STATUS_PORT = 5


def decode_status(data: bytes) -> dict[str, Any]:
    """Decode the fPort 5 status uplink of the battery-powered Dragino sensors."""
    require_length(data, 7)
    return {
        "firmware_version": firmware_version(data[1], data[2]),
        "battery_voltage": u16(data, 5) / 1000,
    }


class DraginoDevice(Device):
    """Decode the uplinks of one Dragino model into typed attributes.

    Subclasses implement `decode`, which returns only the attributes an uplink
    carries; everything else keeps its last value.
    """

    MODEL: ClassVar[str]
    NAMES: ClassVar[tuple[str, ...]] = ()

    battery_voltage: float | None = None
    firmware_version: str | None = None
    rssi: float | None = None
    snr: float | None = None

    def __init__(self, descriptor: DeviceDescriptor) -> None:
        """Start without data until the first uplink arrives."""
        super().__init__(descriptor)
        self._last_uplink_at: datetime | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> dict[str, Any]:
        """Return the attributes carried by an uplink, empty if it is not live data.

        Raises DecodeError when the payload does not match the device layout.
        """
        raise NotImplementedError

    def handle_event(self, event: DeviceEvent) -> None:
        """Apply a decoded uplink and notify once the update is complete."""
        if not isinstance(event, UplinkEvent):
            return
        if self._last_uplink_at is not None and event.received_at < self._last_uplink_at:
            return
        try:
            values = self.decode(event.f_port, event.data)
        except DecodeError as err:
            _LOGGER.debug(
                "Ignoring uplink of %s on port %s: %s",
                self.descriptor.dev_eui,
                event.f_port,
                err,
            )
            return
        if not values:
            return
        self._last_uplink_at = event.received_at
        for name, value in values.items():
            if not hasattr(self, name):
                raise AttributeError(f"{type(self).__name__} has no field {name!r}")
            setattr(self, name, value)
        self._update_signal(event.receptions)
        self.notify()

    def _update_signal(self, receptions: Sequence[GatewayReception]) -> None:
        """Keep the link quality of the strongest gateway reception."""
        measured = [reception for reception in receptions if reception.rssi is not None]
        if measured:
            best = max(measured, key=lambda reception: reception.rssi or 0)
            self.rssi = best.rssi
            self.snr = best.snr
