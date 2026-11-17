"""Build a pinned or latest-stable HA test environment using uv (Linux/WSL)."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent


def fetch_package(package: str, version: str | None = None) -> dict[str, Any]:
    """Fetch PyPI metadata; a missing matching harness must fail, not fall back."""
    suffix = f"/{version}" if version else ""
    with urlopen(f"https://pypi.org/pypi/{package}{suffix}/json", timeout=30) as response:
        metadata: dict[str, Any] = json.load(response)
    return metadata


def read_requirements(text: str) -> list[str]:
    """Read the repository's exact dependency pins."""
    requirements = [
        line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")
    ]
    if not all(re.fullmatch(r"[a-zA-Z0-9_-]+==[a-zA-Z0-9.+-]+", line) for line in requirements):
        raise ValueError("requirements_test.txt must contain exact package==version pins")
    return requirements


def select_version(target: str, requirements: list[str]) -> str:
    """Choose the pinned HA release or the current stable HA release."""
    if target == "latest":
        version = str(fetch_package("homeassistant")["info"]["version"])
    else:
        version = next(
            requirement.split("==")[1]
            for requirement in requirements
            if requirement.startswith("homeassistant==")
        )
    if not re.fullmatch(r"\d{4}\.\d+\.\d+", version):
        raise ValueError(f"Expected a stable Home Assistant release, got {version!r}")
    return version


def python_requirement(requires_python: str) -> str:
    """Use HA's minimum Python minor, including its patch floor and other bounds."""
    if not (match := re.search(r">=\s*(\d+)\.(\d+)", requires_python)):
        raise ValueError(f"Cannot determine HA's Python runtime from {requires_python!r}")
    major, minor = (int(value) for value in match.groups())
    return f"{requires_python},<{major}.{minor + 1}"


def environment_requirements(target: str, requirements: list[str], version: str) -> list[str]:
    """Keep tool pins; only the latest lane replaces the HA and LoRaWAN pins."""
    if target == "pinned":
        return requirements
    selected = [
        requirement
        for requirement in requirements
        if not requirement.startswith(
            ("homeassistant==", "pytest-homeassistant==", "lorawan-connection==")
        )
    ]
    return [*selected, f"pytest-homeassistant=={version}", f"homeassistant=={version}"]


def setup_environment(target: str, venv: Path) -> None:
    """Create an isolated environment, leaving existing environments untouched."""
    if venv.exists():
        raise FileExistsError(f"Refusing to overwrite existing environment: {venv}")
    requirements = read_requirements((ROOT / "requirements_test.txt").read_text())
    version = select_version(target, requirements)
    runtime = python_requirement(fetch_package("homeassistant", version)["info"]["requires_python"])
    # Check that the exact matching harness exists before creating the environment.
    fetch_package("pytest-homeassistant", version)
    print(f"Testing {target}: Home Assistant {version}, Python {runtime}", flush=True)
    subprocess.run(["uv", "venv", "--managed-python", "--python", runtime, str(venv)], check=True)
    python = venv / "bin" / "python"
    install = ["uv", "pip", "install", "--python", str(python)]
    subprocess.run([*install, *environment_requirements(target, requirements, version)], check=True)
    if target == "latest":
        manifest = json.loads(
            subprocess.check_output(
                [
                    str(python),
                    "-c",
                    "import json, pathlib, sysconfig; "
                    "print((pathlib.Path(sysconfig.get_path('purelib')) / "
                    "'homeassistant/components/lorawan/manifest.json').read_text())",
                ],
                text=True,
            )
        )
        runtime_requirements = manifest["requirements"]
        if not runtime_requirements:
            raise ValueError("The installed LoRaWAN integration declares no requirements")
        subprocess.run([*install, *runtime_requirements], check=True)
    versions = subprocess.check_output(
        [
            str(python),
            "-c",
            "import importlib.metadata as m, platform; "
            "print('Python ' + platform.python_version()); "
            "print('\\n'.join(p + '==' + m.version(p) for p in "
            "('homeassistant', 'pytest-homeassistant', 'lorawan-connection')))",
        ],
        text=True,
    )
    print(versions, end="")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as file:
            file.write(f"### Home Assistant: {target}\n\n```text\n{versions}```\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("pinned", "latest"), required=True)
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv")
    arguments = parser.parse_args()
    setup_environment(arguments.target, arguments.venv.resolve())
