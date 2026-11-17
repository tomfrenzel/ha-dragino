"""Request documented status and measurement uplinks."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DraginoConfigEntry
from .const import DOMAIN
from .dragino_lorawan import Cpl03Lb, Lht65n, Lt22222l, T68dl
from .entity import DraginoEntity, DraginoEntityDescription, async_setup_platform_entities


@dataclass(frozen=True, kw_only=True)
class DraginoButtonDescription(DraginoEntityDescription, ButtonEntityDescription):
    """Describe a request without implying that a response has arrived."""

    payload: bytes


DESCRIPTIONS = (
    DraginoButtonDescription(
        key="request_device_status",
        translation_key="request_device_status",
        device_types=(Cpl03Lb, Lht65n, T68dl),
        value_fn=lambda _: None,
        entity_category=EntityCategory.DIAGNOSTIC,
        payload=b"\x26\x01",
    ),
    DraginoButtonDescription(
        key="request_measurement",
        translation_key="request_measurement",
        device_types=(Lt22222l,),
        value_fn=lambda _: None,
        entity_category=EntityCategory.DIAGNOSTIC,
        payload=b"\x08\xff",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DraginoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Only add requests documented for the corresponding model."""
    async_setup_platform_entities(entry, async_add_entities, DESCRIPTIONS, DraginoRequestButton)


class DraginoRequestButton(DraginoEntity, ButtonEntity):
    """Queue an uplink request."""

    entity_description: DraginoButtonDescription

    @override
    async def async_press(self) -> None:
        """Ask the device for a report in its next available receive window."""
        if (
            isinstance(self.device, Lht65n)
            and (version := self.device.firmware_version) is not None
            and tuple(int(part) for part in version.split(".")) < (1, 4, 0)
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="status_requires_firmware",
                translation_placeholders={"version": "1.4.0"},
            )
        await self.async_queue_command(self.entity_description.payload)
