"""Helpers shared by the Dragino tests."""

from lorawan_connection import AddedEvent, DeviceDescriptor
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.dragino.dragino_lorawan import DEVICES, DraginoDevice
from custom_components.dragino.dragino_lorawan.device import BRAND_IDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

STACK_MODELS = [
    pytest.param(stack, model, id=f"{stack}-{model.MODEL}")
    for stack in BRAND_IDS
    for model in DEVICES
    if stack in model.identifiers
]


async def async_setup_devices(
    hass: HomeAssistant,
    connection: MockConnection,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    *descriptors: DeviceDescriptor,
) -> None:
    """Set up the integration for devices the connection already knows."""
    for descriptor in descriptors:
        connection.emit(AddedEvent(descriptor=descriptor, received_at=dt_util.utcnow()))
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def entity_states(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    dev_eui: str = "0201010101010101",
    *,
    domains: tuple[str, ...] = ("sensor", "binary_sensor"),
) -> dict[str, float | str]:
    """Return enabled entity states by key, selecting measurement platforms by default."""
    registry = er.async_get(hass)
    prefix = f"network:{dev_eui}:"
    states: dict[str, float | str] = {}
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        if entry.disabled or not entry.unique_id.startswith(prefix) or entry.domain not in domains:
            continue
        state = hass.states.get(entry.entity_id)
        assert state is not None, entry.entity_id
        key = entry.unique_id.removeprefix(prefix)
        try:
            states[key] = float(state.state)
        except ValueError:
            states[key] = state.state
    return states


def descriptor_for(
    model: type[DraginoDevice],
    stack: str = "chirpstack",
    *,
    dev_eui: str = "0201010101010101",
    name: str = "Test",
) -> DeviceDescriptor:
    """Describe a device the way a connection reports it for a catalog entry.

    ChirpStack also reports the catalog model name; The Things Stack does not.
    """
    brand_id, model_id = model.identifiers[stack]
    return DeviceDescriptor(
        network_id="network",
        dev_eui=dev_eui,
        name=name,
        application_id="application",
        profile_id="local-profile",
        stack=stack,
        brand_id=brand_id,
        model_id=model_id,
        model=model.MODEL if stack == "chirpstack" else "",
    )
