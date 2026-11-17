"""Verify that compatibility CI tests the requested HA release and its runtime."""

from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError

import pytest

from scripts import setup_test_environment as setup

PINS = [
    "homeassistant==2026.11.2",
    "pytest-homeassistant==2026.11.2",
    "lorawan-connection==1.3.2",
    "ruff==0.17.5",
    "mypy==2.4.1",
]


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        (">=3.14.2", ">=3.14.2,<3.15"),
        (">=3.15.1,!=3.15.2", ">=3.15.1,!=3.15.2,<3.16"),
    ],
)
def test_python_requirement_follows_ha(requirement: str, expected: str) -> None:
    """Keep the patch floor/exclusions without accidentally testing a newer Python minor."""
    assert setup.python_requirement(requirement) == expected


def test_latest_release_ignores_pinned_harness() -> None:
    """A new HA release is selected even if the repository has not been updated."""
    with patch.object(
        setup, "fetch_package", return_value={"info": {"version": "2027.2.0"}}
    ) as fetch:
        assert setup.select_version("latest", PINS) == "2027.2.0"
        fetch.assert_called_once_with("homeassistant")
    assert setup.environment_requirements("latest", PINS, "2027.2.0") == [
        "ruff==0.17.5",
        "mypy==2.4.1",
        "pytest-homeassistant==2027.2.0",
        "homeassistant==2027.2.0",
    ]


def test_pinned_release_preserves_proposed_updates() -> None:
    """The pinned lane tests the dependency versions being proposed by a PR."""
    pins = [
        "homeassistant==2027.1.1",
        "pytest-homeassistant==2027.1.1",
        "lorawan-connection==1.4.0",
        "ruff==0.18.0",
    ]
    with patch.object(setup, "fetch_package") as fetch:
        assert setup.select_version("pinned", pins) == "2027.1.1"
        fetch.assert_not_called()
    assert setup.environment_requirements("pinned", pins, "2027.1.1") == pins


@pytest.mark.parametrize("version", ["2027.1.0b1", "2027.1.0.dev1", "not-a-version"])
def test_latest_never_silently_selects_a_prerelease(version: str) -> None:
    """A surprising PyPI response fails instead of producing a misleading stable check."""
    with (
        patch.object(setup, "fetch_package", return_value={"info": {"version": version}}),
        pytest.raises(ValueError, match="stable Home Assistant release"),
    ):
        setup.select_version("latest", PINS)


def test_matching_harness_is_required(tmp_path: Path) -> None:
    """Never claim compatibility by silently falling back to an older HA/harness."""
    with (
        patch.object(setup, "select_version", return_value="2027.2.0"),
        patch.object(
            setup,
            "fetch_package",
            side_effect=[
                {"info": {"requires_python": ">=3.15.1"}},
                HTTPError("https://pypi.org", 404, "No matching harness", {}, None),
            ],
        ),
        patch.object(setup.subprocess, "run") as run,
        pytest.raises(HTTPError),
    ):
        setup.setup_environment("latest", tmp_path / "venv")
    run.assert_not_called()


def test_latest_installs_ha_runtime_dependency(tmp_path: Path) -> None:
    """Use the selected HA wheel's LoRaWAN requirement, not the repository's stale pin."""
    venv = tmp_path / "venv"
    python = str(venv / "bin" / "python")
    with (
        patch.object(setup, "select_version", return_value="2027.2.0"),
        patch.object(
            setup, "fetch_package", return_value={"info": {"requires_python": ">=3.15.1"}}
        ),
        patch.object(setup.subprocess, "run") as run,
        patch.object(
            setup.subprocess,
            "check_output",
            side_effect=['{"requirements": ["lorawan-connection==2.0.0"]}', "versions\n"],
        ),
        patch.dict(setup.os.environ, {}, clear=True),
    ):
        setup.setup_environment("latest", venv)
    assert run.call_args_list[0] == call(
        ["uv", "venv", "--managed-python", "--python", ">=3.15.1,<3.16", str(venv)],
        check=True,
    )
    assert run.call_args_list[-1] == call(
        ["uv", "pip", "install", "--python", python, "lorawan-connection==2.0.0"], check=True
    )


def test_existing_environment_is_never_overwritten(tmp_path: Path) -> None:
    """Running locally must not destroy the developer's existing Windows or WSL venv."""
    fetch = Mock()
    with (
        patch.object(setup, "fetch_package", fetch),
        pytest.raises(FileExistsError, match="Refusing to overwrite"),
    ):
        setup.setup_environment("latest", tmp_path)
    fetch.assert_not_called()
