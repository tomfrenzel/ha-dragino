"""Test user setup and LoRaWAN discovery."""

from dataclasses import replace
from unittest.mock import patch

from lorawan_connection import AddedEvent, DeviceDescriptor
from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.dragino.dragino_lorawan import DEVICES, DraginoDevice
from homeassistant.components.lorawan import LoRaWANDiscoveryInfo
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from .common import STACK_MODELS, descriptor_for

SOURCES = [(SOURCE_USER, None), (SOURCE_INTEGRATION_DISCOVERY, LoRaWANDiscoveryInfo())]


@pytest.mark.parametrize(("source", "data"), SOURCES)
@pytest.mark.parametrize(("stack", "model"), STACK_MODELS)
async def test_setup(
    hass: HomeAssistant,
    source: str,
    data: LoRaWANDiscoveryInfo | None,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    stack: str,
    model: type[DraginoDevice],
) -> None:
    """Both entry points accept every supported model on either backend."""
    mock_connection.emit(
        AddedEvent(descriptor=descriptor_for(model, stack), received_at=dt_util.utcnow())
    )
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init(
        "dragino", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    with patch("custom_components.dragino.async_setup_entry", return_value=None) as setup:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Dragino"
    assert result["data"] == {}
    assert result["result"].unique_id == "dragino"
    setup.assert_called_once()


@pytest.mark.parametrize(("source", "data"), SOURCES)
@pytest.mark.usefixtures("config_entry")
async def test_already_configured(
    hass: HomeAssistant, source: str, data: LoRaWANDiscoveryInfo | None
) -> None:
    """Only one Dragino entry is needed for all connections."""
    result = await hass.config_entries.flow.async_init(
        "dragino", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(("source", "data"), SOURCES)
async def test_no_connections(
    hass: HomeAssistant, source: str, data: LoRaWANDiscoveryInfo | None
) -> None:
    """Explain that a LoRaWAN backend must be configured first."""
    result = await hass.config_entries.flow.async_init(
        "dragino", context={"source": source}, data=data
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_lorawan_connections"


async def test_empty_connection(hass: HomeAssistant, connection_entry: MockConfigEntry) -> None:
    """A backend without devices cannot create a Dragino entry."""
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init("dragino", context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_supported_devices"


@pytest.mark.parametrize(
    ("brand_id", "model_id", "model"),
    [
        (676, "unknown-uuid", "LDS01"),
        (999, "eaaf6138-870f-48d3-b0ec-299350cb88af", "LDDS75"),
        (999, "unknown", "CPL03-LB"),
    ],
    ids=["unsupported-dragino-model", "other-brand-same-uuid", "other-brand-same-name"],
)
async def test_unsupported_device(
    hass: HomeAssistant,
    connection_entry: MockConfigEntry,
    mock_connection: MockConnection,
    brand_id: int,
    model_id: str,
    model: str,
) -> None:
    """Only models of this integration, from the Dragino catalog, allow setup."""
    descriptor: DeviceDescriptor = replace(
        descriptor_for(DEVICES[0]), brand_id=brand_id, model_id=model_id, model=model
    )
    mock_connection.emit(AddedEvent(descriptor=descriptor, received_at=dt_util.utcnow()))
    assert await hass.config_entries.async_setup(connection_entry.entry_id)
    result = await hass.config_entries.flow.async_init("dragino", context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_supported_devices"
