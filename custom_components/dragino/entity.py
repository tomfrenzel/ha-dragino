"""Entity base class and platform setup shared by all Dragino platforms."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, override

from lorawan_connection import ConnectionUnavailable, DownlinkError

from homeassistant.components.lorawan import LoRaWANEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DraginoConfigEntry
from .const import DOMAIN
from .coordinator import DraginoCoordinator
from .dragino_lorawan import DraginoDevice

DOWNLINK_TIMEOUT = 30


@dataclass(frozen=True, kw_only=True)
class DraginoEntityDescription(EntityDescription):
    """Select a typed value from the device model.

    A dynamic entity is created once the device reports a value for it, so
    optional hardware such as an external probe only shows up when present.
    """

    device_types: tuple[type[DraginoDevice], ...]
    value_fn: Callable[[Any], Any]
    dynamic: bool = False


class DraginoEntity(LoRaWANEntity[DraginoDevice]):
    """Home Assistant entity representing a Dragino device datapoint."""

    coordinator: DraginoCoordinator
    entity_description: DraginoEntityDescription

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    async def async_queue_command(self, data: bytes) -> None:
        """Queue a command without waiting for a sleeping Class A device."""
        if not self.available:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="device_unavailable"
            )
        try:
            async with asyncio.timeout(DOWNLINK_TIMEOUT):
                await self.device.async_send_downlink(data=data, f_port=2, wait_for_ack=False)
        except (DownlinkError, ConnectionUnavailable) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="downlink_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="downlink_timeout"
            ) from err


@callback
def async_setup_platform_entities(
    entry: DraginoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    descriptions: Sequence[DraginoEntityDescription],
    create_entity: Callable[[DraginoCoordinator, Any], DraginoEntity],
) -> None:
    """Create entities for existing and newly discovered devices."""

    @callback
    def added(coordinator: DraginoCoordinator) -> None:
        created: set[str] = set()

        @callback
        def create_missing_entities() -> None:
            device = coordinator.data
            missing = [
                description
                for description in descriptions
                if description.key not in created
                and isinstance(device, description.device_types)
                and (not description.dynamic or description.value_fn(device) is not None)
            ]
            created.update(description.key for description in missing)
            async_add_entities(create_entity(coordinator, description) for description in missing)

        create_missing_entities()
        entry.async_on_unload(coordinator.async_add_listener(create_missing_entities))

    entry.async_on_unload(entry.runtime_data.subscribe_coordinator_added(added))
