"""Test the payload decoders on their own."""

import random
from typing import Any

import pytest

from custom_components.dragino.dragino_lorawan import (
    DEVICES,
    Cpl03Lb,
    DecodeError,
    DraginoDevice,
    Ldds75,
    Lds02,
    Lht65n,
    Lt22222l,
    Lwl02,
    T68dl,
)


@pytest.mark.parametrize("model", DEVICES, ids=lambda model: model.MODEL)
def test_decoders_never_fail_unexpectedly(model: type[DraginoDevice]) -> None:
    """Any payload decodes to known attributes or is rejected as a DecodeError."""
    generator = random.Random(model.MODEL)
    for f_port in range(16):
        for length in range(21):
            for _ in range(20):
                data = generator.randbytes(length)
                try:
                    values = model.decode(f_port, data)
                except DecodeError:
                    continue
                assert isinstance(values, dict)
                for key in values:
                    assert hasattr(model, key), (model.MODEL, f_port, data.hex(), key)


@pytest.mark.parametrize(
    ("model", "f_port"),
    [
        (Ldds75, 2),
        (Lds02, 10),
        (Lwl02, 10),
        (Lht65n, 2),
        (T68dl, 2),
        (Lt22222l, 2),
        (Cpl03Lb, 2),
        (Cpl03Lb, 6),
    ],
)
def test_empty_payload_is_rejected(model: type[DraginoDevice], f_port: int) -> None:
    """A measurement port without data is an error, not an empty measurement."""
    with pytest.raises(DecodeError):
        model.decode(f_port, b"")


@pytest.mark.parametrize("model", DEVICES, ids=lambda model: model.MODEL)
def test_unrelated_ports_carry_no_measurement(model: type[DraginoDevice]) -> None:
    """Configuration and other ports are skipped silently."""
    assert model.decode(200, bytes(range(11))) == {}


@pytest.mark.parametrize("model", [T68dl, Lht65n, Cpl03Lb])
def test_status_port(model: type[DraginoDevice]) -> None:
    """The status uplink reports the firmware and the battery."""
    assert model.decode(5, bytes([0x2B, 0x01, 0x12, 0x00, 0xFF, 0x0B, 0xB8])) == {
        "firmware_version": "1.1.2",
        "battery_voltage": 3.0,
    }


@pytest.mark.parametrize("distance", [0, 20])
def test_ldds75_without_valid_reading(distance: int) -> None:
    """The sensor reports 0 without a sensor and 20 for an invalid measurement."""
    values = Ldds75.decode(2, bytes([13, 10, 0, distance, 0, 0, 0, 1]))
    assert values["distance"] is None
    assert values["battery_voltage"] == 3.338


def test_ldds75_negative_temperature() -> None:
    """The temperature is a signed value in tenths of a degree."""
    assert Ldds75.decode(2, bytes([13, 10, 7, 233, 0, 0xFF, 0x9C, 1]))["temperature"] == -10


def test_lds02_status_bits_do_not_change_the_battery() -> None:
    """The two high bits of the voltage carry the door and leak status."""
    values = Lds02.decode(10, bytes([0xCB, 0x88, 3, 0, 0, 0, 0, 0, 0, 1]))
    assert values["battery_voltage"] == 2.952
    assert values["door_open"] is True
    assert values["water_leak"] is True
    assert values["alarm"] is True


def test_lds02_unknown_mode_reports_only_the_battery() -> None:
    """Modes added by newer firmware must not break the decoding of the battery."""
    values = Lds02.decode(10, bytes([11, 136, 9, 0, 0, 1, 0, 0, 2, 1]))
    assert values["battery_voltage"] == 2.952
    assert values["mode"] == 9
    assert all(
        values[key] is None for key in ("door_open", "door_open_count", "water_leak", "alarm")
    )


@pytest.mark.parametrize("flags", [0x40, 0x80, 0xC0])
def test_lht65n_history_frames_are_skipped(flags: int) -> None:
    """Polled and retransmitted frames must not overwrite the live measurement."""
    assert Lht65n.decode(2, bytes([203, 198, 0, 130, 0, 242, flags | 1, 8, 202, 127, 255])) == {}


def test_lht65n_negative_temperature() -> None:
    """Temperatures below zero are two's complement."""
    values = Lht65n.decode(2, bytes([203, 198, 0xFF, 0x38, 0, 242, 1, 127, 255, 127, 255]))
    assert values["temperature"] == -2.0


def test_lht65n_probe_unplugged() -> None:
    """The reading of an empty probe input is no temperature."""
    values = Lht65n.decode(2, bytes([203, 198, 0, 130, 0, 242, 1, 127, 255, 127, 255]))
    assert values["external_temperature"] is None
    assert values["external_sensor"] == 1


def test_lht65n_external_sht31() -> None:
    """The external SHT31 reports temperature and humidity."""
    values = Lht65n.decode(2, bytes([203, 198, 0, 130, 0, 242, 11, 9, 96, 1, 244]))
    assert values["external_temperature"] == 24.0
    assert values["external_humidity"] == 50.0


def test_lht65n_external_sht31_missing() -> None:
    """Without the SHT31 both of its values are unknown."""
    values = Lht65n.decode(2, bytes([203, 198, 0, 130, 0, 242, 11, 127, 255, 0, 0]))
    assert values["external_temperature"] is None
    assert values["external_humidity"] is None


def test_lht65n_interrupt_frame_needs_15_bytes() -> None:
    """The interrupt layout differs in length from the other 11-byte layouts."""
    base = [203, 198, 0, 130, 0, 242, 4]
    with pytest.raises(DecodeError):
        Lht65n.decode(2, bytes([*base, 1, 0, 0, 5]))
    values = Lht65n.decode(2, bytes([*base, 1, 0, 0, 0, 5, 0, 0, 0]))
    assert values["interrupt_level"] is True
    assert values["count"] == 5


def test_lht65n_resets_external_values_between_frames() -> None:
    """Every frame states all external values, so removed hardware goes unknown."""
    values = Lht65n.decode(2, bytes([203, 198, 0, 130, 0, 242, 1, 127, 255, 127, 255]))
    assert {
        key: values[key]
        for key in ("illuminance", "adc_voltage", "count", "interrupt_level", "pir_activity")
    } == dict.fromkeys(("illuminance", "adc_voltage", "count", "interrupt_level", "pir_activity"))


def test_lht65n_32_bit_counter_is_unsigned() -> None:
    """Counters beyond 2**31 must not turn negative."""
    values = Lht65n.decode(2, bytes([203, 198, 0, 130, 0, 242, 8, 0x80, 0, 0, 1]))
    assert values["count"] == 0x80000001


def test_t68dl_thresholds() -> None:
    """The alarm byte carries the high and low temperature flags."""
    values = T68dl.decode(2, bytes([14, 28, 0xFF, 0x38, 3, 101, 83, 241, 0]))
    assert values["temperature"] == -2.0
    assert values["temperature_high"] is True
    assert values["temperature_low"] is True


def test_lt22222l_trigger_mode_reports_only_inputs() -> None:
    """The trigger mode carries the digital inputs but no analog data."""
    values = Lt22222l.decode(2, bytes([0, 0, 0x0A, 0, 0, 0, 0, 0, 0, 0, 6]))
    assert values["work_mode"] == "trigger"
    assert values["di1"] is True
    assert values["di2"] is True
    assert values["avi1"] is None
    assert values["do1"] is None


def test_lt22222l_count_mode() -> None:
    """The counting modes report unsigned 32-bit counters."""
    values = Lt22222l.decode(2, bytes([0, 0, 1, 0, 0, 0, 0, 7, 0, 0, 2]))
    assert values["work_mode"] == "count_1"
    assert values["count1"] == 256
    assert values["count2"] == 7


def test_lt22222l_unknown_mode_has_no_work_mode() -> None:
    """New firmware modes are tolerated."""
    assert Lt22222l.decode(2, bytes(11))["work_mode"] is None


def test_cpl03lb_contact_status_requires_data() -> None:
    """The contact status port is a single byte of flags."""
    with pytest.raises(DecodeError):
        Cpl03Lb.decode(7, b"")


@pytest.mark.parametrize("suffix", [b"", b"\x01"])
def test_cpl03lb_pulse_port(suffix: bytes) -> None:
    """Both the original ten-byte and newer ROC-flag frames carry three counters."""
    values = Cpl03Lb.decode(6, bytes.fromhex("08 00 00 05 00 00 06 ff ff ff") + suffix)
    assert values["work_mode"] == "cpl03"
    assert (values["pa8_count"], values["pa4_count"], values["pb15_count"]) == (5, 6, 0xFFFFFF)
    assert values["contact_open"] is None


def test_cpl03lb_truncated_pulse_frame() -> None:
    """A missing counter byte must not become a zero count."""
    with pytest.raises(DecodeError):
        Cpl03Lb.decode(6, bytes(9))


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (0x00, (True, True, True)),
        (0x15, (False, False, False)),
        (0x04, (True, False, True)),
    ],
)
def test_cpl03lb_contact_status(flags: int, expected: tuple[bool, bool, bool]) -> None:
    """A set bit is a closed contact on this port."""
    values: dict[str, Any] = Cpl03Lb.decode(7, bytes([flags]))
    assert (values["pa8_open"], values["pa4_open"], values["pb15_open"]) == expected


def test_cpl03lb_modes_clear_the_other_mode_values() -> None:
    """A mode change must not leave stale values of the other mode behind."""
    cpl03 = Cpl03Lb.decode(2, bytes([0x08, 0, 0, 5, 0, 0, 6, 0, 0, 7, 0]))
    cpl01 = Cpl03Lb.decode(2, bytes([0x01, 0, 0, 5, 0, 0, 6, 0, 0, 7, 0]))
    assert cpl03["contact_open"] is None
    assert cpl03["pulse_count"] is None
    assert cpl01["pa8_count"] is None
    assert cpl01["contact_open"] is True
