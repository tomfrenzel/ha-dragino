# Contributing and maintenance

Run commands from the repository root. Home Assistant does not run natively on Windows;
use Linux or WSL.

## Development

```bash
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
pytest tests
ruff check . && ruff format --check .
mypy custom_components/dragino --strict --ignore-missing-imports
```

The payload decoders live in `custom_components/dragino/dragino_lorawan/` and are ported from
the vendor JavaScript decoders. `tests/test_golden.py` checks them against the vendor decoders'
output stored in `tests/golden/vectors.json`. To regenerate the vectors, run
`node tests/golden/generate.mjs` with `CATALOG_CODECS` pointing at the `codecs` folder of
[`chirpstack-device-profiles/vendors/dragino`](https://github.com/chirpstack/chirpstack-device-profiles/tree/master/vendors/dragino).

Keep the upstream MIT copyright notice in both license copies when distributing decoder
ports derived from `chirpstack-device-profiles`.

## Home Assistant compatibility tests

The **Test** workflow runs on pushes, pull requests, every day at 05:23 UTC, and manually.
Both environments are required to pass:

- **Pinned:** the versions in `requirements_test.txt`, including dependency changes proposed
  by Dependabot.
- **Latest:** the latest stable `homeassistant` release from PyPI, the exact matching
  `pytest-homeassistant` release, and the LoRaWAN library required by that installed HA release.
  The tooling pins are retained.

Each environment uses the Python minor required by its HA release, respecting its minimum
patch version. The resolved versions are recorded in the workflow summary. Both run the full
test suite, Ruff and strict mypy. A missing matching test harness is a failure, not a fallback
to an older HA release. Enable GitHub Actions failure notifications for scheduled failures.

To reproduce the latest check on Linux/WSL with `uv` installed:

```bash
python3 scripts/setup_test_environment.py --target latest --venv /tmp/ha-dragino-latest
/tmp/ha-dragino-latest/bin/python -m pytest tests -q
/tmp/ha-dragino-latest/bin/ruff check .
/tmp/ha-dragino-latest/bin/ruff format --check .
/tmp/ha-dragino-latest/bin/mypy custom_components/dragino --strict --ignore-missing-imports
```

Choose a new environment path; the setup script refuses to overwrite an existing one.