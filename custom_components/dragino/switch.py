"""Control LT-22222-L outputs without changing any other channel."""

from dataclasses import dataclass
from operator import attrgetter
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DraginoConfigEntry
from .dragino_lorawan import Lt22222l
from .entity import DraginoEntity, DraginoEntityDescription, async_setup_platform_entities


@dataclass(frozen=True, kw_only=True)
class DraginoSwitchDescription(DraginoEntityDescription, SwitchEntityDescription):
    """Describe an output and its channel-preserving commands."""

    on_payload: bytes
    off_payload: bytes


DESCRIPTIONS = tuple(
    DraginoSwitchDescription(
        key=f"{output}_control",
        translation_key=output,
        device_types=(Lt22222l,),
        value_fn=attrgetter(output),
        on_payload=bytes.fromhex(on_payload),
        off_payload=bytes.fromhex(off_payload),
    )
    for output, on_payload, off_payload in (
        ("do1", "02 01 11 11", "02 00 11 11"),
        ("do2", "02 11 01 11", "02 11 00 11"),
        ("ro1", "03 01 11", "03 00 11"),
        ("ro2", "03 11 01", "03 11 00"),
    )
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DraginoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add controls alongside the existing read-only output sensors."""
    async_setup_platform_entities(entry, async_add_entities, DESCRIPTIONS, DraginoOutputSwitch)


class DraginoOutputSwitch(DraginoEntity, SwitchEntity):
    """Show reported state only; an accepted downlink is not device confirmation."""

    entity_description: DraginoSwitchDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the last uplink's output state."""
        value: bool | None = self.entity_description.value_fn(self.device)
        return value

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Close the relay or pull the digital output low."""
        await self.async_queue_command(self.entity_description.on_payload)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Open the relay or release the digital output."""
        await self.async_queue_command(self.entity_description.off_payload)
