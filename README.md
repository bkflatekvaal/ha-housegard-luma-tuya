# Housegard Luma

A Home Assistant custom integration for Housegard Luma gateways and paired
smoke alarms, heat alarms and remote controllers. It uses the existing Home
Assistant Tuya integration and its cloud push connection.

This repository is a publication preparation snapshot, not yet a completed HACS
release. See [release preparation](RELEASE_PREPARATION.md) before publishing.

## Requirements and setup

- A Luma gateway available in the official Home Assistant Tuya integration.
- Gateway product ID `s3x3xmgbeohtvm40` (shared product metadata, not a device ID).
- The development installation runs Home Assistant 2026.9.4. Compatibility with
  older versions is not established; this integration uses Tuya runtime internals.

For manual installation, copy only `custom_components/housegard_luma` into your
Home Assistant `custom_components` directory, restart Home Assistant, then add
**Housegard Luma** in Settings → Devices & services and select the gateway.
No additional Tuya credentials or local keys are requested by this integration.
After the repository is published and validated, add
`https://github.com/bkflatekvaal/ha-housegard-luma-tuya` as a HACS custom repository
of type Integration, download it, restart Home Assistant, and add Housegard Luma.
This does not imply inclusion in HACS's default catalog.

## Features

- Automatic discovery and persistent gateway-local subdevice identity.
- Smoke, Heat and Tamper binary sensors; Battery, raw RSSI and Last seen sensors.
- Online state from verified inventory and supported Online events.
- Gateway Devices, Online devices and Offline devices counts. Offline count
  includes inventory records not confirmed Online; per-device unknown remains
  distinguishable.
- Per-alarm Locate, and gateway Refresh devices, Network Test and Sound Test.
- Last-known state restoration. Persisted active alarms require a verified clear.

Gateway metadata is Housegard / WS2GW-R. Smoke and Heat use generic Luma class
names because the available protocol cannot establish an exact commercial model.
The remote retains the independently identified Luma RC350 name.

Locate, Network Test and Sound Test have been user-verified in the development
installation. Sound Test is audible. Setup requests inventory, not an alarm test.
The main remaining live check is automatic Online → Offline → Online and count
updates without manually pressing Refresh devices. No live tests are run by CI.

## Current limitations

- RC350 outbound group Test/Locate/Hush is not implemented.
- Incoming RC350 diagnostic classification matches a small set of exact observed
  strings, including their generic Norwegian remote label. It is not generalized
  to other names, indexes or firmware, and supplies no runtime device association.
- Network Test completion/final-byte semantics are unresolved; count sensors use
  inventory, not aggregate result frames.
- RSSI is an uncalibrated raw value, not dBm. Unknown state remains unknown.
- This is a community integration, not an official Housegard product.

## Diagnostics and privacy

Diagnostics include raw protocol captures. These can contain device/room names,
gateway identifiers and event timestamps even when other fields are redacted.
Base64 encoding is not anonymization. Review and sanitize diagnostics before
sharing them publicly; do not upload Home Assistant backups or `.storage` files.

## Development

Use Python 3.13 and an isolated environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/housegard_luma
python -m ruff check custom_components/housegard_luma tests/housegard_luma
python -m ruff format --check custom_components/housegard_luma tests/housegard_luma
python -m compileall -q custom_components/housegard_luma tests/housegard_luma
```

Public tests use artificial labels and generated packets. They are behavioral
regressions, not new captured protocol evidence. The original exact capture suite
is held separately by the maintainer and is not distributed in this repository.
