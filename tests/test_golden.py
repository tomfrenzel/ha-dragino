"""Compare the Python decoders with the vendor JavaScript decoders.

vectors.json holds the output of the vendor decoders for many payloads; regenerate
it with tests/golden/generate.mjs. Fields the integration does not expose, such as
timestamps and threshold flags, are ignored.
"""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.dragino.dragino_lorawan import (
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

VECTORS: dict[str, list[dict[str, Any]]] = json.loads(
    (Path(__file__).parent / "golden" / "vectors.json").read_text()
)

NO_PROBE = 327.67

LT_WORK_MODES = {
    "2ACI+2AVI": "2aci_2avi",
    "Count mode 1": "count_1",
    "2ACI+1Count": "2aci_1count",
    "Count mode 2": "count_2",
    " 1ACI+2AVI+1Count": "1aci_2avi_1count",
    "Trigger mode": "trigger",
}

Expectation = dict[str, Any] | None


def _present(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _map(js: dict[str, Any], fields: dict[str, tuple[str, Callable[[Any], Any]]]) -> dict[str, Any]:
    return {name: convert(js[key]) for key, (name, convert) in fields.items() if key in js}


def _same(value: Any) -> Any:
    return value


def _firmware_and_battery(js: dict[str, Any]) -> dict[str, Any]:
    return _map(
        js,
        {
            "FIRMWARE_VERSION": ("firmware_version", _same),
            "BAT": ("battery_voltage", _same),
        },
    )


def _ldds75(f_port: int, data: list[int], js: dict[str, Any]) -> Expectation:
    distance = js["Distance"]
    return {
        "battery_voltage": js["Bat"],
        "distance": distance if isinstance(distance, int) else None,
        "temperature": float(js["TempC_DS18B20"]),
    }


def _contact(f_port: int, data: list[int], js: dict[str, Any] | None) -> Expectation:
    if len(data) != 10:
        return None
    if js is None:
        # The vendor decoder skips unknown modes; the integration still keeps the battery.
        return {"battery_voltage": ((data[0] << 8 | data[1]) & 0x3FFF) / 1000, "mode": data[2]}
    return _map(
        js,
        {
            "BAT_V": ("battery_voltage", _same),
            "MOD": ("mode", _same),
            "DOOR_OPEN_STATUS": ("door_open", bool),
            "DOOR_OPEN_TIMES": ("door_open_count", _same),
            "LAST_DOOR_OPEN_DURATION": ("last_door_open_duration", _same),
            "WATER_LEAK_STATUS": ("water_leak", bool),
            "WATER_LEAK_TIMES": ("water_leak_count", _same),
            "LAST_WATER_LEAK_DURATION": ("last_water_leak_duration", _same),
            "ALARM": ("alarm", bool),
        },
    )


def _lht65n(f_port: int, data: list[int], js: dict[str, Any]) -> Expectation:
    if f_port == 5:
        return _firmware_and_battery(js)
    if data[6] & 0xC0:
        return {}
    expected = _map(
        js,
        {
            "BatV": ("battery_voltage", _same),
            "TempC_SHT": ("temperature", _same),
            "Hum_SHT": ("humidity", _same),
            "TempC_DS": ("external_temperature", _same),
            "TempC_TMP117": ("external_temperature", _same),
            "Ext_TempC_SHT": ("external_temperature", _same),
            "Ext_Hum_SHT": ("external_humidity", _same),
            "ILL_lx": ("illuminance", _same),
            "ADC_V": ("adc_voltage", _same),
            "Exit_count": ("count", _same),
            "Move_count": ("count", _same),
        },
    )
    expected["external_sensor"] = data[6] & 0x0F
    if "Exti_pin_level" in js:
        # Interrupt mode reports High/Low, PIR mode Activity/No activity.
        expected["interrupt_level" if data[6] & 0x0F == 4 else "pir_activity"] = js[
            "Exti_pin_level"
        ] in ("High", "Activity")
    if data[6] & 0x0F == 8:
        # The vendor decoder reads the 32-bit counter as signed.
        expected["count"] &= 0xFFFFFFFF
    if expected.get("external_temperature", 0) >= NO_PROBE:
        # Without a probe the whole external reading is meaningless.
        expected["external_temperature"] = None
        expected["external_humidity"] = None
    return expected


def _lt22222l(f_port: int, data: list[int], js: dict[str, Any]) -> Expectation:
    if f_port == 5:
        return _map(js, {"FIRMWARE_VERSION": ("firmware_version", _same)})
    trigger = js.get("Work_mode") == "Trigger mode"
    levels = {"True": True, "False": False} if trigger else {"H": True, "L": False}
    expected = _map(
        js,
        {
            "Work_mode": ("work_mode", LT_WORK_MODES.get),
            "AVI1_V": ("avi1", _same),
            "AVI2_V": ("avi2", _same),
            "ACI1_mA": ("aci1", _same),
            "ACI2_mA": ("aci2", _same),
            "Count1_times": ("count1", _same),
            "Count2_times": ("count2", _same),
            "DI1_status": ("di1", levels.get),
            "DI2_status": ("di2", levels.get),
            "DO1_status": ("do1", lambda value: value == "L"),
            "DO2_status": ("do2", lambda value: value == "L"),
            "RO1_status": ("ro1", lambda value: value == "ON"),
            "RO2_status": ("ro2", lambda value: value == "ON"),
        },
    )
    if "Work_mode" not in js:
        expected["work_mode"] = None
    return expected


def _t68dl(f_port: int, data: list[int], js: dict[str, Any]) -> Expectation:
    if f_port == 5:
        return _firmware_and_battery(js)
    return _map(
        js,
        {
            "BatV": ("battery_voltage", _same),
            "TempC": ("temperature", _same),
            "TEMPH_flag": ("temperature_high", lambda value: value == "True"),
            "TEMPL_flag": ("temperature_low", lambda value: value == "True"),
        },
    )


def _cpl03lb(f_port: int, data: list[int], js: dict[str, Any] | None) -> Expectation:
    if js is None:
        return None
    if f_port == 5:
        return _firmware_and_battery(js)
    if f_port == 7:
        return _map(
            js,
            {
                "EXTI_PA8_Status": ("pa8_open", lambda value: value == "OPEN"),
                "EXTI_PA4_Status": ("pa4_open", lambda value: value == "OPEN"),
                "EXTI_PB15_Status": ("pb15_open", lambda value: value == "OPEN"),
            },
        )
    return _map(
        js,
        {
            "WORKMOD": ("work_mode", str.lower),
            "PIN_STATUS": ("contact_open", lambda value: value == "OPEN"),
            "ALARM": ("alarm", lambda value: value == "TRUE"),
            "TOTAL_PULSE": ("pulse_count", _same),
            "LAST_DURATION": ("last_duration", _same),
            "PA8_TOTAL_PULSE": ("pa8_count", _same),
            "PA4_TOTAL_PULSE": ("pa4_count", _same),
            "PB15_TOTAL_PULSE": ("pb15_count", _same),
        },
    )


MODELS: dict[str, tuple[type[DraginoDevice], Callable[..., Expectation]]] = {
    "ldds75": (Ldds75, _ldds75),
    "lds02": (Lds02, _contact),
    "lwl02": (Lwl02, _contact),
    "lht65n": (Lht65n, _lht65n),
    "t68dl": (T68dl, _t68dl),
    "lt22222l": (Lt22222l, _lt22222l),
    "cpl03lb": (Cpl03Lb, _cpl03lb),
}

CASES = [
    pytest.param(device, case, id=f"{device}-{index}-port{case['f_port']}")
    for device in MODELS
    for index, case in enumerate(VECTORS[device])
]


@pytest.mark.parametrize(("device", "case"), CASES)
def test_matches_vendor_decoder(device: str, case: dict[str, Any]) -> None:
    """Every value the vendor decoder reports is decoded identically."""
    model, expect = MODELS[device]
    data = bytes(case["data"])
    assert "error" not in case["js"], case["js"]
    expected = expect(case["f_port"], case["data"], case["js"]["data"])

    if expected is None:
        with pytest.raises(DecodeError):
            model.decode(case["f_port"], data)
        return

    actual = _present(model.decode(case["f_port"], data))
    assert actual == pytest.approx(_present(expected))
