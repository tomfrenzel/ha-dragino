"""Test the entities created for each Dragino model."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from lorawan_connection import (
    ConnectionUnavailable,
    GatewayReception,
    RemovedEvent,
    UplinkEvent,
)
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator

from custom_components.dragino.const import DOMAIN
from custom_components.dragino.dragino_lorawan import (
    Cpl03Lb,
    DraginoDevice,
    Ldds75,
    Lds02,
    Lht65n,
    Lt22222l,
    Lwl02,
    T68dl,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import async_setup_devices, descriptor_for, entity_states


def uplink(
    model: type[DraginoDevice],
    f_port: int,
    data: list[int],
    *,
    stack: str = "chirpstack",
    age: float = 0,
    receptions: tuple[GatewayReception, ...] = (),
) -> UplinkEvent:
    """Create an uplink of the test device received `age` seconds ago."""
    return UplinkEvent(
        descriptor=descriptor_for(model, stack),
        received_at=dt_util.utcnow() - timedelta(seconds=age),
        f_port=f_port,
        data=bytes(data),
        receptions=receptions,
    )


# The first five payloads are the examples of the ChirpStack device catalog.
CASES = [
    pytest.param(
        Ldds75,
        2,
        [13, 10, 7, 233, 0, 0, 0, 1],
        {"battery_voltage": 3.338, "distance": 2025, "temperature": 0},
        id="ldds75",
    ),
    pytest.param(
        Lds02,
        10,
        [11, 136, 1, 0, 27, 179, 0, 0, 0, 0],
        {
            "battery_voltage": 2.952,
            "door_open": "off",
            "door_open_count": 7091,
            "last_door_open_duration": 0,
            "alarm": "off",
        },
        id="lds02",
    ),
    pytest.param(
        Lwl02,
        10,
        [12, 30, 2, 0, 0, 4, 0, 0, 0, 0],
        {
            "battery_voltage": 3.102,
            "water_leak": "off",
            "water_leak_count": 4,
            "last_water_leak_duration": 0,
        },
        id="lwl02",
    ),
    pytest.param(
        Lht65n,
        2,
        [203, 198, 0, 130, 0, 242, 1, 127, 255, 127, 255],
        {"battery_voltage": 3.014, "temperature": 1.3, "humidity": 24.2},
        id="lht65n",
    ),
    pytest.param(
        T68dl,
        2,
        [14, 28, 9, 246, 0, 101, 83, 241, 0],
        {
            "battery_voltage": 3.612,
            "temperature": 25.5,
            "temperature_high": "off",
            "temperature_low": "off",
        },
        id="t68dl",
    ),
    pytest.param(
        Lht65n,
        2,
        [203, 198, 0, 130, 0, 242, 1, 8, 202, 127, 255],
        {
            "battery_voltage": 3.014,
            "temperature": 1.3,
            "humidity": 24.2,
            "external_temperature": 22.5,
        },
        id="lht65n-external-probe",
    ),
    pytest.param(
        Lds02,
        10,
        [139, 136, 3, 0, 0, 0, 0, 0, 0, 1],
        {
            "battery_voltage": 2.952,
            "door_open": "on",
            "water_leak": "off",
            "alarm": "on",
        },
        id="lds02-door-and-leak",
    ),
    pytest.param(
        Lt22222l,
        2,
        [12, 228, 3, 232, 15, 160, 78, 32, 137, 0, 1],
        {
            "work_mode": "2aci_2avi",
            "avi1": 3.3,
            "avi2": 1.0,
            "aci1": 4.0,
            "aci2": 20.0,
            "di1": "on",
            "di2": "off",
            "do1": "on",
            "do2": "off",
            "ro1": "on",
            "ro2": "off",
        },
        id="lt22222l",
    ),
    pytest.param(
        Cpl03Lb,
        2,
        [0x08, 0, 0, 5, 0, 0, 6, 0, 0, 7, 0],
        {"work_mode": "cpl03", "pa8_count": 5, "pa4_count": 6, "pb15_count": 7},
        id="cpl03lb-three-contact",
    ),
    pytest.param(
        Cpl03Lb,
        2,
        [0x03, 0, 1, 0, 0, 0, 30, 0, 0, 0, 0],
        {
            "work_mode": "cpl01",
            "contact_open": "on",
            "alarm": "on",
            "pulse_count": 256,
            "last_duration": 30,
        },
        id="cpl03lb-single-contact",
    ),
]

LHT65N_PLAIN = [203, 198, 0, 130, 0, 242, 1, 127, 255, 127, 255]
LHT65N_PROBE = [203, 198, 0, 130, 0, 242, 1, 8, 202, 127, 255]


@pytest.mark.parametrize("image", ["icon.png", "logo.png"])
async def test_local_brand_images(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, image: str
) -> None:
    """The actual Home Assistant endpoint serves the bundled PNG, not a placeholder."""
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()
    response = await client.get(f"/api/brands/integration/dragino/{image}?placeholder=no")
    assert response.status == 200
    assert response.content_type == "image/png"
    expected = await hass.async_add_executor_job(
        (
            Path(__file__).parent.parent / "custom_components" / "dragino" / "brand" / image
        ).read_bytes
    )
    assert await response.read() == expected


STACK_CASES = [
    pytest.param(stack, *case.values, id=f"{stack}-{case.id}")
    for case in CASES
    for stack in ("chirpstack", "tts")
    if stack == "chirpstack" or stack in case.values[0].identifiers
]


@pytest.mark.parametrize(("stack", "model", "f_port", "data", "expected"), STACK_CASES)
async def test_entities(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    stack: str,
    model: type[DraginoDevice],
    f_port: int,
    data: list[int],
    expected: dict[str, float | str],
) -> None:
    """An uplink creates the entities of its model and reports its values."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(model, stack)
    )
    assert config_entry.state is ConfigEntryState.LOADED

    mock_connection.emit(uplink(model, f_port, data, stack=stack))
    await hass.async_block_till_done()

    assert entity_states(hass, config_entry) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (Ldds75, {"distance", "temperature"}),
        (Lds02, {"door_open"}),
        (Lwl02, {"water_leak"}),
        (Lht65n, {"temperature", "humidity"}),
        (T68dl, {"temperature", "temperature_high", "temperature_low"}),
        (Lt22222l, set()),
        (Cpl03Lb, set()),
    ],
)
async def test_entities_before_first_uplink(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    model: type[DraginoDevice],
    expected: set[str],
) -> None:
    """Only datapoints every unit of the model has exist until data arrives."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(model)
    )

    assert entity_states(hass, config_entry) == dict.fromkeys(expected, "unknown")


async def test_device(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The device is registered for its LoRaWAN identity."""
    await async_setup_devices(
        hass,
        mock_connection,
        connection_entry,
        config_entry,
        descriptor_for(Ldds75, name="Cellar"),
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "network:0201010101010101"), config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Cellar"
    assert device.manufacturer == "Dragino"
    assert device.model == "LDDS75"


async def test_dynamic_entities(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """Optional hardware gets entities once a frame reports it and keeps them."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Lht65n)
    )

    mock_connection.emit(uplink(Lht65n, 2, LHT65N_PLAIN))
    await hass.async_block_till_done()
    assert "external_temperature" not in entity_states(hass, config_entry)

    mock_connection.emit(uplink(Lht65n, 2, LHT65N_PROBE))
    await hass.async_block_till_done()
    assert entity_states(hass, config_entry)["external_temperature"] == 22.5

    # Unplugging the probe clears its value; the entity stays for a re-plug.
    mock_connection.emit(uplink(Lht65n, 2, LHT65N_PLAIN))
    await hass.async_block_till_done()
    assert entity_states(hass, config_entry)["external_temperature"] == "unknown"


async def test_cpl03lb_contact_status_adds_entities(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """Contact states of the three inputs arrive on their own port."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Cpl03Lb)
    )

    mock_connection.emit(uplink(Cpl03Lb, 6, [0x08, 0, 0, 5, 0, 0, 6, 0, 0, 7, 0]))
    mock_connection.emit(uplink(Cpl03Lb, 7, [0x01]))
    await hass.async_block_till_done()

    states = entity_states(hass, config_entry)
    assert states["pa8_count"] == 5
    assert (states["pa8_open"], states["pa4_open"], states["pb15_open"]) == (
        "off",
        "on",
        "on",
    )


async def test_signal_quality_is_disabled_by_default(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    entity_registry: er.EntityRegistry,
) -> None:
    """RSSI and SNR of the best gateway are available but opt-in."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Ldds75)
    )

    mock_connection.emit(
        uplink(
            Ldds75,
            2,
            [13, 10, 7, 233, 0, 0, 0, 1],
            receptions=(
                GatewayReception("a", rssi=-110, snr=-3.5),
                GatewayReception("b", rssi=-92, snr=6.25),
            ),
        )
    )
    await hass.async_block_till_done()

    entries = {
        entry.unique_id.rsplit(":", 1)[1]: entry
        for entry in er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    }
    assert entries["rssi"].disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entries["snr"].disabled_by is er.RegistryEntryDisabler.INTEGRATION

    entity_registry.async_update_entity(entries["rssi"].entity_id, disabled_by=None)
    entity_registry.async_update_entity(entries["snr"].entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_connection.emit(
        uplink(
            Ldds75,
            2,
            [13, 10, 7, 233, 0, 0, 0, 1],
            receptions=(
                GatewayReception("a", rssi=-110, snr=-3.5),
                GatewayReception("b", rssi=-92, snr=6.25),
            ),
        )
    )
    await hass.async_block_till_done()

    states = entity_states(hass, config_entry)
    assert states["rssi"] == -92
    assert states["snr"] == 6.25


async def test_unavailable_on_disconnect(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """Entities cannot be trusted once the connection is lost."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Ldds75)
    )
    mock_connection.emit(uplink(Ldds75, 2, [13, 10, 7, 233, 0, 0, 0, 1]))
    await hass.async_block_till_done()

    mock_connection.disconnect()
    await hass.async_block_till_done()

    assert set(entity_states(hass, config_entry).values()) == {STATE_UNAVAILABLE}


async def test_removed_device(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device deleted from the LoRaWAN server disappears from Home Assistant."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Ldds75)
    )
    assert entity_states(hass, config_entry)

    mock_connection.emit(
        RemovedEvent(descriptor=descriptor_for(Ldds75), received_at=dt_util.utcnow())
    )
    await hass.async_block_till_done()

    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


async def test_devices_of_other_integrations_are_ignored(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    entity_registry: er.EntityRegistry,
) -> None:
    """Devices of other vendors on the same connection get no Dragino entities."""
    other = replace(
        descriptor_for(Ldds75, dev_eui="0201010101010102"),
        brand_id=999,
        model_id="x",
        model="X",
    )
    await async_setup_devices(
        hass,
        mock_connection,
        connection_entry,
        config_entry,
        descriptor_for(Ldds75),
        other,
    )

    assert entity_states(hass, config_entry, "0201010101010101")
    assert not entity_states(hass, config_entry, "0201010101010102")


async def test_stale_uplink_is_ignored(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """A late replay of an older uplink must not overwrite newer values."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Ldds75)
    )

    mock_connection.emit(uplink(Ldds75, 2, [13, 10, 7, 233, 0, 0, 0, 1]))
    mock_connection.emit(uplink(Ldds75, 2, [13, 10, 3, 232, 0, 0, 0, 1], age=60))
    await hass.async_block_till_done()

    assert entity_states(hass, config_entry)["distance"] == 2025


@pytest.mark.parametrize(
    ("f_port", "data"),
    [
        (2, [13, 10, 7]),
        (2, []),
        (3, [13, 10, 7, 233, 0, 0, 0, 1]),
    ],
    ids=["truncated", "empty", "unknown-port"],
)
async def test_unusable_uplink_is_ignored(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    f_port: int,
    data: list[int],
) -> None:
    """Malformed frames and ports without live data keep the previous values."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Ldds75)
    )
    mock_connection.emit(uplink(Ldds75, 2, [13, 10, 7, 233, 0, 0, 0, 1]))
    await hass.async_block_till_done()
    before = entity_states(hass, config_entry)

    mock_connection.emit(uplink(Ldds75, f_port, data))
    await hass.async_block_till_done()

    assert entity_states(hass, config_entry) == before


async def test_unload(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unloading unavailable-marks entities and a reload restores them."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(Ldds75)
    )
    entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    ]
    assert entity_ids

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert all(hass.states.get(entity_id).state == STATE_UNAVAILABLE for entity_id in entity_ids)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert entity_states(hass, config_entry) == {
        "distance": "unknown",
        "temperature": "unknown",
    }


async def test_setup_retries_while_connection_is_unavailable(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """The entry waits for connections that cannot be subscribed to yet."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    with patch.object(mock_connection, "async_subscribe", side_effect=ConnectionUnavailable):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
