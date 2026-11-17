"""Request the periodic reporting interval over LoRaWAN."""

from dataclasses import dataclass
import math
from typing import override

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DraginoConfigEntry
from .const import DOMAIN
from .dragino_lorawan import DEVICES
from .entity import DraginoEntity, DraginoEntityDescription, async_setup_platform_entities

MIN_INTERVAL = 1
MAX_INTERVAL = 0xFFFFFF


@dataclass(frozen=True, kw_only=True)
class DraginoNumberDescription(DraginoEntityDescription, NumberEntityDescription):
    """Describe a requested device setting."""


DESCRIPTION = DraginoNumberDescription(
    key="requested_reporting_interval",
    translation_key="requested_reporting_interval",
    device_types=DEVICES,
    value_fn=lambda _: None,
    entity_category=EntityCategory.CONFIG,
    native_unit_of_measurement=UnitOfTime.SECONDS,
    native_min_value=MIN_INTERVAL,
    native_max_value=MAX_INTERVAL,
    native_step=1,
    mode=NumberMode.BOX,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DraginoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an interval control for each supported model."""
    async_setup_platform_entities(entry, async_add_entities, (DESCRIPTION,), DraginoIntervalNumber)


class DraginoIntervalNumber(DraginoEntity, NumberEntity):
    """Track only the last successfully queued interval, not a confirmed setting."""

    entity_description: DraginoNumberDescription
    _attr_assumed_state = True

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Encode whole seconds as an unsigned, big-endian three-byte interval."""
        if (
            not math.isfinite(value)
            or not MIN_INTERVAL <= value <= MAX_INTERVAL
            or value != int(value)
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_interval",
                translation_placeholders={"min": str(MIN_INTERVAL), "max": str(MAX_INTERVAL)},
            )
        await self.async_queue_command(b"\x01" + int(value).to_bytes(3, "big"))
        self._attr_native_value = value
        self.async_write_ha_state()
