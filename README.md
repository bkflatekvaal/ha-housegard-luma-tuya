# Housegard Luma

![Housegard](custom_components/housegard_luma/brand/logo.svg)

A custom Home Assistant integration for Housegard Luma gateways and their paired
smoke alarms, heat alarms, and the Luma RC350 remote. The integration uses the
existing official Tuya integration and its cloud push connection; it does not add
its own separate credentials, local keys, or custom cloud client.

Community integration, version **0.1.1**, with core v1 functionality complete.
See [CHANGELOG.md](CHANGELOG.md) for release notes. This repository can be used
as a HACS custom repository; it is not listed in the default HACS catalog.

## What it does

The component discovers Housegard devices that appear behind a Tuya gateway and
tracks their state using the gateway's existing Tuya runtime.

Only Housegard Luma hardware is currently live tested. LINKD smoke detector
protocol type `0x17` has provisional support with the same behavior as `0x02`;
confirmation on LINKD hardware is pending ([issue #1](https://github.com/bkflatekvaal/ha-housegard-luma-tuya/issues/1)).

Tested Housegard hardware:

| Tested hardware | Home Assistant model |
| --- | --- |
| Housegard Luma GW650 gateway | Luma GW650 |
| Housegard Luma Smoke Alarm class | Luma Smoke Alarm |
| Housegard Luma Heat Alarm class | Luma Heat Alarm |
| Housegard Luma RC350 remote | Luma RC350 |

Housegard markets the gateway as
[GW650](https://housegard.se/Product/Files/Global/604030%20Manual%20Housegard%20LUMA%20GW650%20Global_1.pdf).
Tuya Device Details identifies the tested gateway's underlying Tuya/OEM model as
`WS2GW-R`, product name `Wireless Interlink Gateway`, category `mal`, and
product ID `s3x3xmgbeohtvm40`. Subdevices are carried in proprietary raw
`sub_admin` records, rather than ordinary independent Tuya device records.

The integration creates a small set of HA entities for each discovered subdevice,
including state and diagnostic entities for the gateway and each alarm.

## Requirements

- Home Assistant with the official Tuya integration already configured and
  connected to the Housegard gateway.
- A Luma gateway available in the Tuya device map.
- The gateway product ID `s3x3xmgbeohtvm40`.
- Home Assistant **2026.9.4 or newer** is the supported baseline. Development
  validation was performed with 2026.9.4; future versions may require changes
  because the integration depends on Tuya runtime internals.

## Installation

### Manual install

1. Clone this repository or download the source for the desired GitHub release.
2. Copy only the folder `custom_components/housegard_luma` into your Home
   Assistant `custom_components` directory.
3. Restart Home Assistant.
4. In Home Assistant, open Settings → Devices & services.
5. Add integration → choose `Housegard Luma`.
6. Select the Luma gateway from the list of Tuya-managed gateways.

The integration does not request additional Tuya credentials or local keys.

The integration bundles Housegard's logo and icon in its `brand/` folder for
Home Assistant 2026.3 and newer. Standard and high-resolution PNGs are rendered
from the original SVGs. Artwork sources: [Housegard logo](https://www.housegard.se/build/static/images/housegard/logo.svg)
and [Housegard icon](https://housegard.se/build/static/favicon/housegard/favicon.svg).
Housegard branding belongs to its respective owner; the repository's MIT license
applies to the integration code, not the third-party artwork. This is a community
integration.

### HACS setup

1. Open HACS and select Custom repositories from its menu.
2. Add `https://github.com/bkflatekvaal/ha-housegard-luma-tuya` with type Integration.
3. Find Housegard Luma in HACS and download it.
4. Restart Home Assistant, then add Housegard Luma from Settings → Devices & services.

For upgrades, update through HACS or replace the integration folder with the
new release's copy, then restart Home Assistant. Keep the official Tuya
integration configured.

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
- RC350 discovery, inventory battery/RSSI, connectivity, and last-seen entities
- Incoming Test/Locate/Hush diagnostic classification by operation vocabulary,
  including the newer Locate `Device SN` variant
- State restoration for previously known alarm states, with explicit verified
  clear events required before a persisted active alarm can be reset

Gateway metadata is reported as Housegard / Luma GW650 without changing the
user's friendly gateway name. Smoke and Heat alarms use
generic Luma class names because the protocol does not reliably expose an exact
commercial model. The remote retains its independently identified `Luma RC350`
name when discovered.

| Device | Entities and actions |
| --- | --- |
| Gateway | Devices, Online devices, Offline devices; Refresh devices, Network Test, Sound Test |
| Smoke alarm | Smoke, Tamper, Online, Battery, RSSI, Last seen; Locate |
| Heat alarm | Heat, Tamper, Online, Battery, RSSI, Last seen; Locate |
| RC350 remote | Online, inventory Battery/RSSI, Last seen; incoming action diagnostics |

Refresh devices requests paired-device inventory, not fresh detector telemetry.
Locate and Sound Test can make alarms sound; commands are sent only when their
buttons are pressed. Sending a command does not confirm its physical execution.
Alarm states are updated from individual detector reports, not command echoes
or remote button logs.

## Other brands / OEM variants

Other products appear to use related Sub-GHz alarm platforms. Compatibility
evidence and implementation status vary by brand:

- **Heiman — strongly related hardware:** Heiman publishes the
  [WS2GW-R gateway](https://www.heimantech.com/product/gateway-ws2gw-series).
  Its [official HA integration](https://github.com/heimanhome/heiman_home)
  uses Heiman Cloud, HTTPS APIs and MQTT; no matching Luma raw protocol was found.
- **Gardia — strongly related / possible OEM (inference):** the
  [Smart HUB 868 MHz](https://www.gardia.no/product/gardia-smart-hub-868-mhz/)
  connects smoke/heat alarms and advertises Tuya/Smart Life app compatibility.
  No WS2GW-R model, product ID or matching raw protocol was established.
- **LINKD — matching Tuya metadata; provisional type `0x17` support:**
  [HA Core issue #163024](https://github.com/home-assistant/core/issues/163024)
  includes diagnostics matching the product ID, category, product name and
  `sub_admin` DP. [Integration issue #1](https://github.com/bkflatekvaal/ha-housegard-luma-tuya/issues/1)
  supplies matching individual-report and inventory framing.
  Type `0x17` uses the existing smoke detector field mappings and Locate command
  provisionally; alarm transitions, telemetry, connectivity, and commands still
  need hardware confirmation. CO support is not implemented here.

Only Housegard Luma hardware is currently live tested. See the
[OEM investigation](docs/oem-platform-investigation-2026-10-05.md) for evidence
and limits. If your gateway appears related, open an issue with its commercial
model, Tuya-reported model, product name/category and redacted diagnostics.
Sanitized inventory/protocol captures may help when appropriate; raw captures
can contain names and serials. Never publish local keys, credentials, tokens,
physical Tuya device/account IDs, MACs, UUIDs, factory serials, IPs or location.

## Current limitations and non-blocking future work

This project is still a community integration and there are important limitations:

- RC350 outbound group Test/Locate/Hush actions still require verified outbound
  Tuya Publish payloads and target semantics. Reviewed physical-button captures
  contain incoming operation logs and `03 07` individual status reports, rather
  than verified outbound commands. Repeated Hush and Locate status reports can
  be identical except for a varying byte at the RSSI position; they do not
  establish an action opcode to replay. Gateway Sound Test and per-alarm Locate
  already have independently verified outbound commands.
  Sound Test (`07 07 FF 02`) may be functionally related to RC350 Test, but
  equivalence has not been protocol-verified.
- Incoming diagnostic classification recognizes known operation vocabulary.
  Names and `SN`/`No` suffixes are treated as opaque input and do not establish
  remote identity, addressing, or a command payload.
- Network Test completion and final-byte semantics are not fully resolved; the
  count sensors are based on inventory data rather than aggregate result frames.
  Observations `07 07 FF 03 0C 01 00` (12 online / 1 offline) and
  `07 07 FF 03 0D 00 00` (13 online / 0 offline) strongly support the count
  interpretation, without proving completion semantics.
- Inventory counts retain devices across partial updates. Offline devices counts
  records that are not known to be online, including unknown connectivity.
- RC350 logs provide diagnostic classification, not Home Assistant device
  triggers or outbound controls.
- RSSI is exposed as a raw protocol value, not a calibrated dBm value.
- Unknown or unsupported states remain unknown rather than being inferred.
- The code is built around the current Tuya runtime and may need adjustments for
  future HA/Tuya SDK changes.

## Online/Offline behavior and live verification

Both automatic connectivity transitions are **live verified / DONE**:

- Online -> Offline without manual Refresh devices.
- Offline -> Online without manual Refresh devices.

Home Assistant follows the connectivity state supplied by Luma/Tuya. Offline
recognition can take a significant amount of time; once Luma/Tuya marks a
detector Offline, Home Assistant follows automatically. Reconnection also
updates automatically. This latency belongs to Luma/Tuya; the integration does
not infer Offline from Last seen age or add a custom heartbeat/timeout.

After restart, restored and cached connectivity remains unknown until fresh
inventory or a supported Online event supplies current evidence. Individual
reports do not establish Online by themselves. Offline counts include retained
inventory records whose connectivity is unknown; there is no separate Unknown
devices entity. RSSI and Last seen remain ordinary diagnostic sensors with
normal Home Assistant updates and history.

## V1 verification status

Core v1 functionality is considered functionally complete and live verified.
Discovery, inventory across sub_admin and continuation DPs, Refresh devices,
Store/restoration, and multiple gateway isolation are complete. Battery, raw
RSSI, Last seen, Online/Offline, and Tamper/Recovery are implemented and verified.
Smoke and Heat Triggered/Restored behavior distinguishes physical/self tests
from real alarms, including the verified real Heat Triggered -> Alarm Restored
sequence. This does not add a separate Test event entity or device trigger.

Per-alarm Locate is live verified for Smoke and Heat and dynamically targets the
inventory index. Gateway Network Test and Sound Test are implemented and live
verified, including successful Sound Test from Home Assistant. Refresh devices
and gateway device counts are also live verified. The verified Network Test
and Sound Test commands remain `07 07 FF 03 3C` and `07 07 FF 02`,
respectively. Setup/reload sends one inventory query (`02 07`) after restoration
and platform setup; it never automatically sends Locate, Network Test, or Sound
Test. Explicit Refresh presses request inventory subject to the existing
in-flight guard and cooldown.

Physical incoming RC350 Test, Locate, and Hush/Silence actions are verified.
They provide diagnostic classification; outbound RC350-equivalent group
controls and robust Operation-log-only routing across remotes/re-pairing are
future work.

## Diagnostics and privacy

Downloaded diagnostics include redacted subdevice state, gateway model,
inventory counts/freshness, framing information, and operation classifications.
They exclude gateway IDs, device names, raw Base64/hex payloads, decoded text,
and opaque inventory headers, which can contain personal identifiers. The
integration does not export Tuya account data, local keys, tokens, IP addresses,
MACs, factory serials, UUIDs, or location. Bounded raw captures remain internal
for runtime processing; ordinary diagnostics exports do not include them.

Review diagnostics before sharing them publicly. Do not upload Home Assistant
backups or `.storage` files to public issue reports or community support threads.

## Troubleshooting

- **No gateway offered:** confirm the gateway is available in the official Tuya
  integration and uses product ID `s3x3xmgbeohtvm40`. Already configured gateways
  are excluded from the selection list.
- **After manually reloading Tuya or reauthenticating:** reload Housegard Luma
  afterward so it binds to the replacement Tuya manager. Normal MQ reconnects
  within the existing manager are followed automatically.
- **Missing devices:** press Refresh devices and allow up to 15 seconds for the
  response. Requests have a 30-second cooldown. Partial inventory responses
  retain previously discovered devices.
- **Unknown or unavailable values:** the protocol has not supplied a verified
  value, or the Tuya gateway/transport is unavailable. Inventory does not refresh
  Last seen; that timestamp requires an individual subdevice report.

Report problems through [GitHub issues](https://github.com/bkflatekvaal/ha-housegard-luma-tuya/issues)
with the integration and Home Assistant versions, device class, steps to
reproduce, and sanitized diagnostics where relevant.

## Development

Protocol decoding lives in `parser.py`; `registry.py` merges gateway-local
identities and reported state; `storage.py` persists the registry. The
`coordinator.py` module bridges the existing Tuya manager and push connection,
while `capture.py` records bounded diagnostic evidence. Entity platforms use
`entity.py` for push updates and discovery. `operation_log.py` recognizes verified
incoming operation vocabulary; it does not identify an outbound address.

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
behavioral regression coverage. Public test names and `SN`/`No` suffixes are
synthetic. Runtime classification contains no installation-specific names or
captured suffixes. The full private capture suite is not distributed with this
repository.

GitHub Actions runs the public tests, Ruff checks, compilation,
HACS validation, and Home Assistant hassfest. Private evidence is excluded from
Git, CI, and release artifacts.

Before tagging a release, run the checks above and ensure the GitHub Actions
hassfest and HACS jobs pass. Keep the release tag and manifest version aligned;
use `v0.1.1` for this release. HACS installs
directly from the public repository files. Include only public source/tests and
exclude the ignored `PRIVATE/` evidence archive from manually built artifacts.

Confirm repository topics required by HACS validation (such as
`home-assistant`, `hacs`, `housegard`, and `tuya`) and publish a GitHub release for
the chosen tag. No release is published by this audit. See
[the release audit](docs/release-audit-2026-10-05.md) for findings and validation
limits.
