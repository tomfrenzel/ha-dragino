"""Binary sensors for Dragino devices."""

from dataclasses import dataclass
from operator import attrgetter
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DraginoConfigEntry
from .dragino_lorawan import Cpl03Lb, DraginoDevice, Lds02, Lht65n, Lt22222l, Lwl02, T68dl
from .entity import DraginoEntity, DraginoEntityDescription, async_setup_platform_entities

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DraginoBinarySensorDescription(DraginoEntityDescription, BinarySensorEntityDescription):
    """Describe a binary sensor backed by a device attribute."""


def _flag(
    key: str,
    *device_types: type[DraginoDevice],
    device_class: BinarySensorDeviceClass | None = None,
    dynamic: bool = True,
    translated: bool = True,
) -> DraginoBinarySensorDescription:
    return DraginoBinarySensorDescription(
        key=key,
        translation_key=key if translated else None,
        device_types=device_types,
        value_fn=attrgetter(key),
        dynamic=dynamic,
        device_class=device_class,
    )


DESCRIPTIONS: tuple[DraginoBinarySensorDescription, ...] = (
    _flag(
        "door_open",
        Lds02,
        device_class=BinarySensorDeviceClass.DOOR,
        dynamic=False,
        translated=False,
    ),
    _flag("door_open", Lwl02, device_class=BinarySensorDeviceClass.DOOR, translated=False),
    _flag(
        "water_leak",
        Lwl02,
        device_class=BinarySensorDeviceClass.MOISTURE,
        dynamic=False,
        translated=False,
    ),
    _flag(
        "water_leak",
        Lds02,
        device_class=BinarySensorDeviceClass.MOISTURE,
        translated=False,
    ),
    _flag("alarm", Lds02, Lwl02, Cpl03Lb, device_class=BinarySensorDeviceClass.PROBLEM),
    _flag(
        "temperature_high",
        T68dl,
        device_class=BinarySensorDeviceClass.HEAT,
        dynamic=False,
    ),
    _flag(
        "temperature_low",
        T68dl,
        device_class=BinarySensorDeviceClass.COLD,
        dynamic=False,
    ),
    _flag("interrupt_level", Lht65n),
    _flag(
        "pir_activity",
        Lht65n,
        device_class=BinarySensorDeviceClass.MOTION,
        translated=False,
    ),
    _flag("di1", Lt22222l),
    _flag("di2", Lt22222l),
    _flag("do1", Lt22222l),
    _flag("do2", Lt22222l),
    _flag("ro1", Lt22222l),
    _flag("ro2", Lt22222l),
    _flag(
        "contact_open",
        Cpl03Lb,
        device_class=BinarySensorDeviceClass.OPENING,
        translated=False,
    ),
    _flag("pa8_open", Cpl03Lb, device_class=BinarySensorDeviceClass.OPENING),
    _flag("pa4_open", Cpl03Lb, device_class=BinarySensorDeviceClass.OPENING),
    _flag("pb15_open", Cpl03Lb, device_class=BinarySensorDeviceClass.OPENING),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DraginoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for existing and newly discovered devices."""
    async_setup_platform_entities(entry, async_add_entities, DESCRIPTIONS, DraginoBinarySensor)


class DraginoBinarySensor(DraginoEntity, BinarySensorEntity):
    """Binary sensor for a Dragino device datapoint."""

    entity_description: DraginoBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the last observed state."""
        value: bool | None = self.entity_description.value_fn(self.device)
        return value
