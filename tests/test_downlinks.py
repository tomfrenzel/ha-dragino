"""Verify Home Assistant controls against documented Dragino command bytes."""

import asyncio
from dataclasses import replace
from unittest.mock import patch

from lorawan_connection import ConnectionUnavailable, Downlink, DownlinkError, UplinkEvent
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.dragino.const import DOMAIN
from custom_components.dragino.dragino_lorawan import (
    Cpl03Lb,
    DraginoDevice,
    Lht65n,
    Lt22222l,
    T68dl,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import STACK_MODELS, async_setup_devices, descriptor_for, entity_states

DEV_EUI = "0201010101010101"
CONTROL_DOMAINS = ("button", "number", "switch")


@pytest.fixture
def model() -> type[DraginoDevice]:
    """Use the I/O controller unless a test selects another model."""
    return Lt22222l


@pytest.fixture
async def setup_controls(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    model: type[DraginoDevice],
    stack: str,
) -> None:
    """Load the real integration against a recording connection."""
    await async_setup_devices(
        hass, mock_connection, connection_entry, config_entry, descriptor_for(model, stack)
    )


def control_id(registry: er.EntityRegistry, domain: str, key: str) -> str:
    """Find a control by stable device identity, not its translated name."""
    entity_id = registry.async_get_entity_id(domain, DOMAIN, f"network:{DEV_EUI}:{key}")
    assert entity_id is not None
    return entity_id


@pytest.mark.parametrize(("stack", "model"), STACK_MODELS)
async def test_controls_and_interval(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    entity_registry: er.EntityRegistry,
    setup_controls: None,
    model: type[DraginoDevice],
) -> None:
    """Only supported controls appear; every model queues the interval without an ACK."""
    expected = {"requested_reporting_interval"}
    if model is Lt22222l:
        expected |= {
            "do1_control",
            "do2_control",
            "ro1_control",
            "ro2_control",
            "request_measurement",
        }
    if model in (Cpl03Lb, Lht65n, T68dl):
        expected.add("request_device_status")
    assert entity_states(hass, config_entry, domains=CONTROL_DOMAINS) == dict.fromkeys(
        expected, "unknown"
    )
    assert not mock_connection.downlinks
    entity_id = control_id(entity_registry, "number", "requested_reporting_interval")
    async with asyncio.timeout(2):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": entity_id, "value": 600}, blocking=True
        )
    assert list(mock_connection.downlinks.values()) == [
        Downlink(DEV_EUI, 2, bytes.fromhex("01 00 02 58"), confirmed=False)
    ]
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 600
    assert state.attributes["assumed_state"] is True
    assert state.attributes["unit_of_measurement"] == "s"


@pytest.mark.parametrize(
    ("value", "payload"),
    [(1, "01 00 00 01"), (60, "01 00 00 3c"), (86400, "01 01 51 80"), (16777215, "01 ff ff ff")],
)
async def test_interval_boundaries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockConnection,
    setup_controls: None,
    value: int,
    payload: str,
) -> None:
    """The number uses seconds without truncation, endian reversal or millisecond conversion."""
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": control_id(entity_registry, "number", "requested_reporting_interval"),
            "value": value,
        },
        blocking=True,
    )
    assert list(mock_connection.downlinks.values()) == [
        Downlink(DEV_EUI, 2, bytes.fromhex(payload))
    ]


@pytest.mark.parametrize("value", [0, -1, 16777216, 1.5, float("nan"), float("inf")])
async def test_invalid_interval_not_sent(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockConnection,
    setup_controls: None,
    value: float,
) -> None:
    """Invalid or fractional intervals must fail before contacting the server."""
    entity_id = control_id(entity_registry, "number", "requested_reporting_interval")
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True
        )
    assert not mock_connection.downlinks
    assert hass.states.get(entity_id).state == "unknown"


@pytest.mark.parametrize("stack", ["chirpstack", "tts"])
@pytest.mark.parametrize(
    ("key", "on", "off", "bit"),
    [
        ("ro1_control", "03 01 11", "03 00 11", 0x80),
        ("ro2_control", "03 11 01", "03 11 00", 0x40),
        ("do1_control", "02 01 11 11", "02 00 11 11", 0x01),
        ("do2_control", "02 11 01 11", "02 11 00 11", 0x02),
    ],
)
async def test_output_commands_preserve_other_channels(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockConnection,
    setup_controls: None,
    stack: str,
    key: str,
    on: str,
    off: str,
    bit: int,
) -> None:
    """Unchanged channels use 0x11; only an uplink changes the switch state."""
    entity_id = control_id(entity_registry, "switch", key)
    descriptor = descriptor_for(Lt22222l, stack)

    await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert hass.states.get(entity_id).state == "unknown"
    mock_connection.emit(
        UplinkEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            f_port=2,
            data=bytes([0] * 8 + [bit, 0, 1]),
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    assert hass.states.get(entity_id).state == "on"
    mock_connection.emit(
        UplinkEvent(
            descriptor=descriptor,
            received_at=dt_util.utcnow(),
            f_port=2,
            data=bytes([0] * 10 + [1]),
        )
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "off"
    assert list(mock_connection.downlinks.values()) == [
        Downlink(DEV_EUI, 2, bytes.fromhex(on)),
        Downlink(DEV_EUI, 2, bytes.fromhex(off)),
    ]


@pytest.mark.parametrize(
    ("model", "key", "payload"),
    [
        (Cpl03Lb, "request_device_status", "26 01"),
        (T68dl, "request_device_status", "26 01"),
        (Lht65n, "request_device_status", "26 01"),
        (Lt22222l, "request_measurement", "08 ff"),
    ],
)
async def test_request_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockConnection,
    setup_controls: None,
    key: str,
    payload: str,
) -> None:
    """Buttons send the documented request, not a reset or mode-change command."""
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": control_id(entity_registry, "button", key)},
        blocking=True,
    )
    assert list(mock_connection.downlinks.values()) == [
        Downlink(DEV_EUI, 2, bytes.fromhex(payload))
    ]


@pytest.mark.parametrize("model", [Lht65n])
async def test_old_lht65n_firmware_rejects_status_request(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockConnection,
    setup_controls: None,
) -> None:
    """Do not enqueue an unsupported command when the old firmware is known."""
    mock_connection.emit(
        UplinkEvent(
            descriptor=descriptor_for(Lht65n),
            received_at=dt_util.utcnow(),
            f_port=5,
            data=bytes.fromhex("0b 01 30 01 00 0b b8"),
        )
    )
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": control_id(entity_registry, "button", "request_device_status")},
            blocking=True,
        )
    assert error.value.translation_key == "status_requires_firmware"
    assert not mock_connection.downlinks


@pytest.mark.parametrize(
    ("domain", "service", "key", "extra"),
    [
        ("number", "set_value", "requested_reporting_interval", {"value": 60}),
        ("switch", "turn_on", "ro1_control", {}),
        ("button", "press", "request_measurement", {}),
    ],
)
@pytest.mark.parametrize("error_type", [DownlinkError, ConnectionUnavailable, TimeoutError])
async def test_downlink_failure_is_surfaced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_connection: MockConnection,
    setup_controls: None,
    domain: str,
    service: str,
    key: str,
    extra: dict[str, int],
    error_type: type[Exception],
) -> None:
    """Queue failures are user-facing and never appear to update the hardware."""
    entity_id = control_id(entity_registry, domain, key)
    with (
        patch.object(DraginoDevice, "async_send_downlink", side_effect=error_type("Queue failed")),
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            domain, service, {"entity_id": entity_id, **extra}, blocking=True
        )
    assert error.value.translation_key == (
        "downlink_timeout" if error_type is TimeoutError else "downlink_failed"
    )
    if domain != "button":
        assert hass.states.get(entity_id).state == "unknown"
    assert not mock_connection.downlinks


async def test_unresponsive_server_times_out(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_controls: None,
) -> None:
    """A hung enqueue must not leave the service pending indefinitely."""

    async def stalled_send(**kwargs: object) -> None:
        await asyncio.Event().wait()

    entity_id = control_id(entity_registry, "switch", "ro1_control")
    with (
        patch.object(DraginoDevice, "async_send_downlink", side_effect=stalled_send),
        patch("custom_components.dragino.entity.DOWNLINK_TIMEOUT", 0),
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert error.value.translation_key == "downlink_timeout"


async def test_controls_after_disconnect_and_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
    setup_controls: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reload does not resend settings; disconnection disables every control."""
    entity_id = control_id(entity_registry, "number", "requested_reporting_interval")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": 600}, blocking=True
    )
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unknown"
    assert len(mock_connection.downlinks) == 1

    mock_connection.disconnect()
    await hass.async_block_till_done()
    assert set(entity_states(hass, config_entry, domains=CONTROL_DOMAINS).values()) == {
        "unavailable"
    }
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": 60}, blocking=True
    )
    assert "missing or not currently available" in caplog.text
    assert len(mock_connection.downlinks) == 1


async def test_downlink_targets_selected_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    connection_entry: MockConfigEntry,
    config_entry: MockConfigEntry,
    mock_connection: MockConnection,
) -> None:
    """Two controllers on a connection never receive each other's commands."""
    first = descriptor_for(Lt22222l)
    second = replace(first, dev_eui="0201010101010102", name="Second")
    await async_setup_devices(hass, mock_connection, connection_entry, config_entry, first, second)
    entity_id = entity_registry.async_get_entity_id(
        "switch", DOMAIN, f"network:{second.dev_eui}:ro2_control"
    )
    assert entity_id is not None
    await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert list(mock_connection.downlinks.values()) == [
        Downlink(second.dev_eui, 2, bytes.fromhex("03 11 01"))
    ]
