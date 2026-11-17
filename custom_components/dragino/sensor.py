"""Sensors for Dragino devices."""

from dataclasses import dataclass
from operator import attrgetter
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DraginoConfigEntry
from .dragino_lorawan import Cpl03Lb, DraginoDevice, Ldds75, Lds02, Lht65n, Lt22222l, Lwl02, T68dl
from .dragino_lorawan.lt22222l import WORK_MODES as LT22222L_WORK_MODES
from .entity import DraginoEntity, DraginoEntityDescription, async_setup_platform_entities

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DraginoSensorDescription(DraginoEntityDescription, SensorEntityDescription):
    """Describe a sensor backed by a device attribute."""


def _count(key: str, *device_types: type[DraginoDevice]) -> DraginoSensorDescription:
    """Describe a counter that only ever grows, apart from device resets."""
    return DraginoSensorDescription(
        key=key,
        translation_key=key,
        device_types=device_types,
        value_fn=attrgetter(key),
        dynamic=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
    )


DESCRIPTIONS: tuple[DraginoSensorDescription, ...] = (
    DraginoSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_types=(DraginoDevice,),
        value_fn=attrgetter("battery_voltage"),
        dynamic=True,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=3,
    ),
    DraginoSensorDescription(
        key="rssi",
        device_types=(DraginoDevice,),
        value_fn=attrgetter("rssi"),
        dynamic=True,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    DraginoSensorDescription(
        key="snr",
        translation_key="snr",
        device_types=(DraginoDevice,),
        value_fn=attrgetter("snr"),
        dynamic=True,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    DraginoSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        device_types=(DraginoDevice,),
        value_fn=attrgetter("firmware_version"),
        dynamic=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DraginoSensorDescription(
        key="temperature",
        device_types=(Ldds75, Lht65n, T68dl),
        value_fn=attrgetter("temperature"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DraginoSensorDescription(
        key="humidity",
        device_types=(Lht65n,),
        value_fn=attrgetter("humidity"),
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DraginoSensorDescription(
        key="distance",
        device_types=(Ldds75,),
        value_fn=attrgetter("distance"),
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DraginoSensorDescription(
        key="external_temperature",
        translation_key="external_temperature",
        device_types=(Lht65n,),
        value_fn=attrgetter("external_temperature"),
        dynamic=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DraginoSensorDescription(
        key="external_humidity",
        translation_key="external_humidity",
        device_types=(Lht65n,),
        value_fn=attrgetter("external_humidity"),
        dynamic=True,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DraginoSensorDescription(
        key="illuminance",
        device_types=(Lht65n,),
        value_fn=attrgetter("illuminance"),
        dynamic=True,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DraginoSensorDescription(
        key="adc_voltage",
        translation_key="adc_voltage",
        device_types=(Lht65n,),
        value_fn=attrgetter("adc_voltage"),
        dynamic=True,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _count("count", Lht65n),
    _count("door_open_count", Lds02, Lwl02),
    DraginoSensorDescription(
        key="last_door_open_duration",
        translation_key="last_door_open_duration",
        device_types=(Lds02, Lwl02),
        value_fn=attrgetter("last_door_open_duration"),
        dynamic=True,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    _count("water_leak_count", Lds02, Lwl02),
    DraginoSensorDescription(
        key="last_water_leak_duration",
        translation_key="last_water_leak_duration",
        device_types=(Lds02, Lwl02),
        value_fn=attrgetter("last_water_leak_duration"),
        dynamic=True,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    DraginoSensorDescription(
        key="work_mode",
        translation_key="lt22222l_work_mode",
        device_types=(Lt22222l,),
        value_fn=attrgetter("work_mode"),
        dynamic=True,
        device_class=SensorDeviceClass.ENUM,
        options=list(LT22222L_WORK_MODES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    *(
        DraginoSensorDescription(
            key=key,
            translation_key=key,
            device_types=(Lt22222l,),
            value_fn=attrgetter(key),
            dynamic=True,
            device_class=device_class,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=3,
        )
        for key, device_class, unit in (
            ("avi1", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            ("avi2", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            ("aci1", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.MILLIAMPERE),
            ("aci2", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.MILLIAMPERE),
        )
    ),
    _count("count1", Lt22222l),
    _count("count2", Lt22222l),
    DraginoSensorDescription(
        key="work_mode",
        translation_key="cpl03_work_mode",
        device_types=(Cpl03Lb,),
        value_fn=attrgetter("work_mode"),
        dynamic=True,
        device_class=SensorDeviceClass.ENUM,
        options=["cpl01", "cpl03"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _count("pulse_count", Cpl03Lb),
    DraginoSensorDescription(
        key="last_duration",
        translation_key="last_duration",
        device_types=(Cpl03Lb,),
        value_fn=attrgetter("last_duration"),
        dynamic=True,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    _count("pa8_count", Cpl03Lb),
    _count("pa4_count", Cpl03Lb),
    _count("pb15_count", Cpl03Lb),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DraginoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for existing and newly discovered devices."""
    async_setup_platform_entities(entry, async_add_entities, DESCRIPTIONS, DraginoSensor)


class DraginoSensor(DraginoEntity, SensorEntity):
    """Sensor for a Dragino device datapoint."""

    entity_description: DraginoSensorDescription

    @property
    @override
    def native_value(self) -> Any:
        """Return the last observed value."""
        return self.entity_description.value_fn(self.device)
