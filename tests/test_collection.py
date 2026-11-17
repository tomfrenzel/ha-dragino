"""Test how Dragino models are matched and fed by a LoRaWAN connection."""

from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock

from lorawan_connection import (
    AddedEvent,
    DeviceDescriptor,
    GatewayReception,
    RemovedEvent,
    UpdatedEvent,
    UplinkEvent,
)
from lorawan_connection.mock import MockConnection
import pytest

from custom_components.dragino.dragino_lorawan import (
    Cpl03Lb,
    DraginoDevice,
    DraginoDeviceCollection,
    Ldds75,
    Lht65n,
)
from homeassistant.util import dt as dt_util

from .common import STACK_MODELS, descriptor_for

DEV_EUI = "0201010101010101"
LDDS75_FRAME = bytes([13, 10, 7, 233, 0, 0, 0, 1])


@pytest.fixture
async def collection(
    mock_connection: MockConnection,
) -> AsyncGenerator[DraginoDeviceCollection]:
    """Collect Dragino devices of the mock connection."""
    collection = DraginoDeviceCollection(mock_connection)
    await collection.async_setup()
    yield collection
    collection.close()


def add(connection: MockConnection, descriptor: DeviceDescriptor) -> None:
    """Announce a device."""
    connection.emit(AddedEvent(descriptor=descriptor, received_at=dt_util.utcnow()))


def send(
    connection: MockConnection,
    data: bytes,
    *,
    model: type[DraginoDevice] = Ldds75,
    f_port: int = 2,
    age: float = 0,
    receptions: tuple[GatewayReception, ...] = (),
) -> None:
    """Deliver an uplink."""
    connection.emit(
        UplinkEvent(
            descriptor=descriptor_for(model),
            received_at=dt_util.utcnow() - timedelta(seconds=age),
            f_port=f_port,
            data=data,
            receptions=receptions,
        )
    )


@pytest.mark.parametrize(("stack", "model"), STACK_MODELS)
async def test_catalog_models_are_matched(
    mock_connection: MockConnection,
    collection: DraginoDeviceCollection,
    stack: str,
    model: type[DraginoDevice],
) -> None:
    """Every model is found through its catalog identity or its name."""
    add(mock_connection, descriptor_for(model, stack))

    assert type(collection.devices[DEV_EUI]) is model


@pytest.mark.parametrize(
    ("stack", "brand_id", "model_id", "model", "expected"),
    [
        ("chirpstack", 676, "new-uuid", "LDDS75", Ldds75),
        ("chirpstack", 676, "new-uuid", "ldds-75", Ldds75),
        ("chirpstack", 676, "new-uuid", "CPL03-LB", Cpl03Lb),
        ("chirpstack", 676, "new-uuid", "cpl03_lb", Cpl03Lb),
        ("chirpstack", 676, "new-uuid", "CPL03", None),
        ("tts", "dragino", "cpl03", "", None),
        ("tts", "dragino", "LHT65N", "", Lht65n),
        ("tts", "dragino", "unknown", "", None),
        ("chirpstack", 676, "new-uuid", "LDS01", None),
        ("chirpstack", 999, "new-uuid", "LDDS75", None),
        ("tts", "other", "ldds75", "", None),
        ("chirpstack", None, "", "LDDS75", None),
    ],
)
async def test_name_fallback(
    mock_connection: MockConnection,
    collection: DraginoDeviceCollection,
    stack: str,
    brand_id: int | str | None,
    model_id: str,
    model: str,
    expected: type[DraginoDevice] | None,
) -> None:
    """Dragino models are recognized by name, but never under another brand."""
    descriptor = replace(
        descriptor_for(Ldds75, stack),
        brand_id=brand_id,
        model_id=model_id,
        model=model,
    )
    add(mock_connection, descriptor)

    device = collection.devices.get(DEV_EUI)
    assert (type(device) if device else None) is expected


async def test_uplink_updates_the_model_once(
    mock_connection: MockConnection, collection: DraginoDeviceCollection
) -> None:
    """Listeners see the complete update of a frame."""
    add(mock_connection, descriptor_for(Ldds75))
    device = collection.devices[DEV_EUI]
    listener = Mock()
    device.add_update_listener(listener)

    send(mock_connection, LDDS75_FRAME)

    listener.assert_called_once_with()
    assert (device.battery_voltage, device.distance, device.temperature) == (3.338, 2025, 0)


@pytest.mark.parametrize(
    ("f_port", "data"),
    [
        (2, LDDS75_FRAME[:5]),
        (2, b""),
        (3, LDDS75_FRAME),
    ],
    ids=["truncated", "empty", "unknown-port"],
)
async def test_unusable_uplink_changes_nothing(
    mock_connection: MockConnection,
    collection: DraginoDeviceCollection,
    f_port: int,
    data: bytes,
) -> None:
    """Frames that carry no live data neither notify nor modify the model."""
    add(mock_connection, descriptor_for(Ldds75))
    device = collection.devices[DEV_EUI]
    listener = Mock()
    device.add_update_listener(listener)

    send(mock_connection, data, f_port=f_port)

    listener.assert_not_called()
    assert device.distance is None


async def test_history_frame_does_not_notify(
    mock_connection: MockConnection, collection: DraginoDeviceCollection
) -> None:
    """Stored LHT65N readings are not the current state."""
    add(mock_connection, descriptor_for(Lht65n))
    device = collection.devices[DEV_EUI]
    listener = Mock()
    device.add_update_listener(listener)

    send(
        mock_connection,
        bytes([203, 198, 0, 130, 0, 242, 0x41, 8, 202, 127, 255]),
        model=Lht65n,
    )

    listener.assert_not_called()
    assert device.temperature is None


async def test_older_uplink_is_ignored(
    mock_connection: MockConnection, collection: DraginoDeviceCollection
) -> None:
    """Delayed delivery must not roll the state back."""
    add(mock_connection, descriptor_for(Ldds75))
    device = collection.devices[DEV_EUI]

    send(mock_connection, LDDS75_FRAME)
    send(mock_connection, bytes([13, 10, 3, 232, 0, 0, 0, 1]), age=60)

    assert device.distance == 2025


async def test_best_gateway_reports_the_signal(
    mock_connection: MockConnection, collection: DraginoDeviceCollection
) -> None:
    """RSSI and SNR belong to the same, strongest, reception."""
    add(mock_connection, descriptor_for(Ldds75))
    device = collection.devices[DEV_EUI]

    send(
        mock_connection,
        LDDS75_FRAME,
        receptions=(
            GatewayReception("a", rssi=-110, snr=-3.5),
            GatewayReception("b", rssi=-92, snr=6.25),
            GatewayReception("c"),
        ),
    )

    assert (device.rssi, device.snr) == (-92, 6.25)


async def test_signal_is_kept_without_receptions(
    mock_connection: MockConnection, collection: DraginoDeviceCollection
) -> None:
    """Uplinks without gateway metadata leave the last signal quality alone."""
    add(mock_connection, descriptor_for(Ldds75))
    device = collection.devices[DEV_EUI]

    send(mock_connection, LDDS75_FRAME, receptions=(GatewayReception("a", -90, 5),))
    send(mock_connection, LDDS75_FRAME)

    assert (device.rssi, device.snr) == (-90, 5)


async def test_reprofiled_device_is_recreated(
    mock_connection: MockConnection, collection: DraginoDeviceCollection
) -> None:
    """Changing the device profile in the server changes the model."""
    add(mock_connection, descriptor_for(Ldds75))
    old = collection.devices[DEV_EUI]

    mock_connection.emit(
        UpdatedEvent(descriptor=descriptor_for(Lht65n), received_at=dt_util.utcnow())
    )

    assert old.closed
    assert type(collection.devices[DEV_EUI]) is Lht65n


async def test_removed_device_is_retired(
    mock_connection: MockConnection, collection: DraginoDeviceCollection
) -> None:
    """Deleting a device closes its model."""
    add(mock_connection, descriptor_for(Ldds75))
    device = collection.devices[DEV_EUI]

    mock_connection.emit(
        RemovedEvent(descriptor=descriptor_for(Ldds75), received_at=dt_util.utcnow())
    )

    assert device.closed
    assert DEV_EUI not in collection.devices
