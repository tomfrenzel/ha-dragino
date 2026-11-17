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
[`chirpstack-device-profiles/vendors/dragino`](https://github.com/tomfrenzel/chirpstack-device-profiles/tree/master/vendors/dragino)
and `CPL03LB_DECODER` pointing at the CPL03-LB decoder.

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

## Dependabot and repository settings

Dependabot checks Python packages daily and GitHub Actions weekly. Home Assistant and its
test harness are grouped so their exact versions stay aligned; other updates use separate PRs.

- **Patch updates:** automatically approved and marked for auto-merge, but only after the
  branch-protection preflight succeeds. GitHub waits for all required checks before merging.
- **Minor and major updates:** never auto-approved or auto-merged; a maintainer must approve
  and merge them in the PR.
- Unknown update types and commits not verified as Dependabot's are not auto-approved.

The privileged auto-merge workflow only reads GitHub metadata; it never checks out or executes
PR code. Reviews are tied to the inspected commit, and merge requests check the head SHA.

The following are **GitHub settings**, not settings that repository files can activate:

1. On the [repository page](https://github.com/tomfrenzel/ha-dragino), edit **About** and add
   topics: `home-assistant`, `hacs`, `custom-integration`, `dragino`, `lorawan`, `chirpstack`,
   `the-things-stack`. HACS checks these repository topics, not a README tag list.
2. Publish the license and workflow files to GitHub and let **Test** and **Validate** run once,
   so their check names are available when configuring protection. The license must be present
   on GitHub for HACS to recognize it.
3. Under [Settings > General](https://github.com/tomfrenzel/ha-dragino/settings), enable
   **Allow squash merging** and **Allow auto-merge**.
4. Under [Settings > Actions > General](https://github.com/tomfrenzel/ha-dragino/settings/actions),
   enable **Allow GitHub Actions to create and approve pull requests**. The default workflow
   token can remain read-only; the auto-merge job requests only the permissions it needs.
5. Under [Settings > Branches](https://github.com/tomfrenzel/ha-dragino/settings/branches),
   add a **classic branch protection rule** for `main`:
   - Require a pull request before merging, with **one approval**.
   - **Dismiss stale pull request approvals when new commits are pushed**.
   - Require status checks **`CI`**, **`HACS`**, and **`Hassfest`**.
   - **Require branches to be up to date before merging**.
   - **Do not allow bypassing the above settings** (including administrators).
   - Leave force pushes and branch deletion disabled.

The `CI` check fails if either matrix environment fails or is cancelled. Do not select the
conditional Dependabot job as a required check. The auto-merge preflight deliberately refuses
unprotected branches or incomplete classic rules; ruleset-only protection is not accepted.
Code-owner or last-push approval requirements may additionally require a human review even for
patches, so leave those options off if you want unattended patch merging.

## Catalogue preview icons

The integration ships `brand/icon.png` and `brand/logo.png` for Home Assistant's local
[brands API](https://contributors.home-assistant.io/blog/2026/02/24/brands-proxy-api/).
This is also the layout accepted by the HACS brand-assets validation.

The pre-installation Marketplace preview is separate. Its
[icon service](https://github.com/home-assistant/brands#marketplace-icons) indexes repositories
from the public HACS integration feed. Adding a custom repository to an individual Home Assistant
instance does not add it to that feed. Follow the
[HACS catalogue inclusion process](https://hacs.xyz/docs/publish/include/) to publish it there;
this requires passing validation, a GitHub release and acceptance into `hacs/default`.

Older HACS frontends use the legacy brands CDN rather than local assets or the Marketplace
icon service. An integration-side manifest change cannot redirect those requests.
