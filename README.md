# Housegard Luma

A custom Home Assistant integration for Housegard Luma gateways and their paired
smoke alarms, heat alarms, and the Luma RC350 remote. The integration uses the
existing official Tuya integration and its cloud push connection; it does not add
its own separate credentials, local keys, or custom cloud client.

This repository is a development/publication snapshot and is not yet a completed
HACS release. See [RELEASE_PREPARATION.md](RELEASE_PREPARATION.md) before
publishing or submitting it to HACS.

## What it does

The component discovers Housegard devices that appear behind a Tuya gateway and
tracks their state using the gateway's existing Tuya runtime.

Supported device classes in the current codebase include:

- Luma gateway (WS2GW-R)
- Smoke alarms
- Heat alarms
- Luma RC350 remote controller

The integration creates a small set of HA entities for each discovered subdevice,
including state and diagnostic entities for the gateway and each alarm.

## Requirements

- Home Assistant with the official Tuya integration already configured and
  connected to the Housegard gateway.
- A Luma gateway available in the Tuya device map.
- The gateway product ID `s3x3xmgbeohtvm40`.
- Development validation has been performed with Home Assistant 2026.9.4.
  Older versions are not guaranteed to be compatible because this integration
  depends on Tuya runtime internals.

## Installation

### Manual install

1. Copy only the folder `custom_components/housegard_luma` into your Home
   Assistant `custom_components` directory.
2. Restart Home Assistant.
3. In Home Assistant, open Settings → Devices & services.
4. Add integration → choose `Housegard Luma`.
5. Select the Luma gateway from the list of Tuya-managed gateways.

The integration does not request additional Tuya credentials or local keys.

### HACS setup

After the repository is published and validated, it can be added as a custom
repository in HACS of type Integration. The repository URL is:

`https://github.com/bkflatekvaal/ha-housegard-luma-tuya`

This does not imply that it is included in HACS's default catalog.

## Features

The current implementation includes these behaviors:

- Automatic discovery and persistent gateway-local subdevice identity
- Smoke, heat, and tamper binary sensors
- Online connectivity state based on verified inventory and supported online
  events
- Battery, raw RSSI, and last-seen sensors
- Inventory counts for total, online, and offline devices
- Per-alarm Locate action
- Gateway actions for Refresh devices, Network Test, and Sound Test
- State restoration for previously known alarm states, with explicit verified
  clear events required before a persisted active alarm can be reset

Gateway metadata is reported as Housegard / WS2GW-R. Smoke and Heat alarms use
generic Luma class names because the protocol does not reliably expose an exact
commercial model. The remote retains its independently identified `Luma RC350`
name when discovered.

## Current limitations and caveats

This project is still a community integration and there are important limitations:

- RC350 outbound group Test/Locate/Hush actions are not implemented.
- Incoming RC350 diagnostic classification is intentionally narrow and matches a
  small set of exact observed strings; it is not generalized across all names,
  indexes, and firmware variants.
- Network Test completion and final-byte semantics are not fully resolved; the
  count sensors are based on inventory data rather than aggregate result frames.
- RSSI is exposed as a raw protocol value, not a calibrated dBm value.
- Unknown or unsupported states remain unknown rather than being inferred.
- The code is built around the current Tuya runtime and may need adjustments for
  future HA/Tuya SDK changes.

## Diagnostics and privacy

Diagnostics may include raw protocol captures and low-level packet information.
These can contain device names, room names, gateway identifiers, and timestamps,
including values that are not fully redacted in some captures.

Base64 encoding is not anonymization. Review and sanitize diagnostics before
sharing them publicly. Do not upload Home Assistant backups or `.storage` files
to public issue reports or community support threads.

## Development

This project uses Python 3.13 and expects an isolated development environment.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/housegard_luma
python -m ruff check custom_components/housegard_luma tests/housegard_luma
python -m ruff format --check custom_components/housegard_luma tests/housegard_luma
python -m compileall -q custom_components/housegard_luma tests/housegard_luma
```

The public test suite uses artificial labels and generated packets; it acts as
behavioral regression coverage and does not include the maintainer's original
private capture set. The exact protocol capture suite used during development is
not distributed with this repository.
