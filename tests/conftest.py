"""Fixtures for Dragino devices and a LoRaWAN connection integration."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from lorawan_connection.mock import MockConnection
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from custom_components.dragino.const import DOMAIN
from homeassistant.components.lorawan import async_register_connection
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant


@pytest.fixture
def stack() -> str:
    """Select the connection's device catalog."""
    return "chirpstack"


@pytest.fixture(autouse=True)
def mock_discovery() -> Generator[None]:
    """Start config flows explicitly instead of scheduling them on registration."""
    with patch("homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"):
        yield


@pytest.fixture
def mock_connection(stack: str) -> MockConnection:
    """Replay devices and emit events without a server."""
    return MockConnection(stack_type=stack)


@pytest.fixture
def connection_integration(hass: HomeAssistant, mock_connection: MockConnection) -> Generator[None]:
    """Provide a connection through the shared integration's public interface."""

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        entry.async_on_unload(
            await async_register_connection(hass, entry, connection=mock_connection)
        )

    async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Unload a config entry."""

    mock_integration(
        hass,
        MockModule(
            "test_connection",
            dependencies=["lorawan"],
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "test_connection.config_flow", Mock())
    with mock_config_flow("test_connection", ConfigFlow):
        yield


@pytest.fixture
def connection_entry(hass: HomeAssistant, connection_integration: None) -> MockConfigEntry:
    """Create the connection integration's entry."""
    entry = MockConfigEntry(domain="test_connection", entry_id="network")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create the single Dragino entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, title="Dragino")
    entry.add_to_hass(hass)
    return entry
