# OEM platform investigation — v0.1.1

Investigated on 2026-10-05 using public documentation, repository source and
public issue diagnostics. No live gateway/account calls were made, no raw
third-party diagnostics were saved, and no OEM detection/support code was added.

## Housegard baseline — VERIFIED

The tested gateway is commercially **Housegard Luma GW650**, confirmed by the
[Housegard GW650 manual](https://housegard.se/Product/Files/Global/604030%20Manual%20Housegard%20LUMA%20GW650%20Global_1.pdf).
The user's Tuya Device Details evidence identifies this same physical gateway
as model `WS2GW-R`, product name `Wireless Interlink Gateway`, product ID
`s3x3xmgbeohtvm40`, category `mal`, `sub: false`. Subdevices are proprietary
raw `sub_admin` records, with inventory continuations `sub_admin1..7`.

HA DeviceInfo is **manufacturer Housegard / model Luma GW650**. The gateway
friendly name and identifiers are retained. Diagnostics show the commercial
`gateway_model` plus technical `gateway_tuya_model: WS2GW-R`.
Smoke/Heat models stay generic; type `02` means Luma Smoke Alarm, `12` Luma Heat
Alarm and `0A` Luma RC350, not exact commercial detector model numbers.

## Heiman — STRONGLY RELATED hardware; compatibility POSSIBLE / UNTESTED

Heiman's [official WS2GW-R product page](https://www.heimantech.com/product/gateway-ws2gw-series)
establishes that designation for a Wi-Fi/Sub-1 GHz gateway with proprietary FSK
radio and an EU 868 MHz variant. A related OEM platform is an inference from the
shared model designation, not proof of identical firmware or Tuya backend.

Reviewed [heimanhome/heiman_home](https://github.com/heimanhome/heiman_home)
at commit `7f8c27247c0de3ca9c737f8286fef6d09e3ef04d`: 17 integration Python/JSON
files, plus eight Python files in its pinned `heiman-connect==1.0.28` package.
Neither scope contained literal matches for `WS2GW-R`, `s3x3xmgbeohtvm40`,
`sub_admin`, `0x02`, `0x12`, `0x0A`, `07 07`, or Luma's inventory/Network
Test/Sound Test Base64 command constants. Literal absence alone cannot exclude
equivalent generated encodings, but the inspected command API uses cloud
properties rather than this integration's Tuya raw DP command structures.

The [API wrapper](https://github.com/heimanhome/heiman_home/blob/7f8c27247c0de3ca9c737f8286fef6d09e3ef04d/custom_components/heiman_home/api.py)
uses `HeimanCloudClient`, `HeimanHttpClient` and `HeimanMqttClient`.
[Cloud constants](https://github.com/heimanhome/heiman_home/blob/7f8c27247c0de3ca9c737f8286fef6d09e3ef04d/custom_components/heiman_home/const.py)
select HTTPS/OAuth endpoints at `spapi.heiman.cn`. The HTTP SDK handles cloud
device/home discovery and control; MQTT handles updates and
[button property writes](https://github.com/heimanhome/heiman_home/blob/7f8c27247c0de3ca9c737f8286fef6d09e3ef04d/custom_components/heiman_home/button.py).
This is HTTPS/REST-style cloud API plus cloud MQTT, not a direct local gateway
connection. The repository advertises smoke/RF hub support and remote
self-test/silence; that does not establish equivalent Luma commands.
Direct support for a Heiman-branded WS2GW-R without modification is not proven.

## Gardia — STRONGLY RELATED / POSSIBLE OEM (inference)

The [Gardia Smart HUB 868 MHz page](https://www.gardia.no/product/gardia-smart-hub-868-mhz/)
describes up to 40 smoke/heat devices, app test/hush and Tuya/Smart Life app
compatibility. Its [official quick guide](https://www.gardia.no/wp-content/uploads/2024/03/Hurtigguide-Gardia-HUBroykvarme-2.pdf)
shows detectors being added behind the Wi-Fi hub. The published commercial
designation is Smart HUB 868 MHz; reviewed material does not establish a numeric
gateway model, WS2GW-R designation, Tuya product ID/category, Wireless Interlink
Gateway name or matching raw DPs/frames. Related architecture is plausible;
same-platform/protocol compatibility remains unverified. Older 433 MHz Gardia
devices are expressly excluded by the current hub's product page.

## LINKD — VERIFIED product metadata match; protocol POSSIBLE / UNTESTED

[HA Core issue #163024](https://github.com/home-assistant/core/issues/163024)
reports missing smoke/heat/CO entities behind a Tuya-visible gateway.
Its attached diagnostics were read in memory with only allowlisted product
metadata, DP mappings and packet shape printed. They match category `mal`,
product name `Wireless Interlink Gateway`, product ID `s3x3xmgbeohtvm40`,
`sub: false`, and DP38 `sub_admin` (also DP26 `alarm_msg`). The reviewed diagnostic
record does not provide an exact gateway model/manufacturer.

The available `sub_admin` snapshot is only three bytes with family `01 07`;
the existing Luma inventory parser correctly reports it as unsupported. It
contains no compatible `02 07` inventory or `03 07` individual report evidence,
and no published equivalent outbound command evidence was established.
The matching product definition is stronger than visual similarity, but cannot
prove packet semantics or CO compatibility. LINKD is a strong future test
candidate, not supported hardware.

## Privacy and compatibility limits

Tuya's [device-details schema](https://developer.tuya.com/en/docs/iot/device-manger?id=K9wj0vb68htna)
distinguishes `product_id` from physical `id`, user `uid`, UUID and secret
`local_key`. The matching ID is generic product-definition metadata already
public in the LINKD diagnostics and integration source; it is appropriate to
document. No physical gateway ID, MAC, UUID, serial, IP, location, credential,
account identifier, raw API Explorer response or raw third-party packet is
included in this investigation document or regression fixtures.

Only Housegard Luma is tested and supported. Safe future reports should supply
commercial/Tuya model and product name/category, redacted diagnostics, and
carefully sanitized protocol evidence where appropriate. Device selection still
requires the existing product ID; that gate is not a compatibility guarantee.

## Release delta and validation

Baseline is local commit `4d1e2ed` (Prepare v0.1.0 release and privacy fixes).
There is no local v0.1.0 tag; the only existing tag is v0.0.2. This v0.1.1 delta
changes gateway model presentation/diagnostics and documentation, with matching
regression assertions and manifest version. Existing discovery, telemetry,
alarms, commands, counts and privacy fixes are not new v0.1.1 features.

Release title and suggested commit message: **v0.1.1** and **Release v0.1.1**.
After reviewing/committing/pushing and passing CI, manually create tag v0.1.1
on the validated commit and publish its GitHub release. No tag, commit or push
was made by this preparation task.

Validation completed for this delta:

| Check | Result |
| --- | --- |
| Current public Luma suite | 73 passed |
| Archived/private suite | 556 passed with `-X utf8`; targets preserved archived source |
| Ruff lint and format | Passed for public and archived source/tests (17 / 69 files) |
| Python compilation | Passed for both source/test trees |
| JSON and manifest consistency | Five JSON files parsed; metadata/version regression check passed |
| Git diff whitespace | Passed |
| hassfest | Unavailable: `script.hassfest` not installed; existing CI job remains required |
| HACS validation | Unavailable: no local HACS validator or Docker; existing CI job remains required |

Reviewed the complete pending diff and public tracked/untracked file list (33
text files). No credentials or user-specific identifiers were found; the only
automated IP-pattern match was an existing SVG path coordinate, not an IP.
No private evidence/generated paths are in the public file list, and nothing
is staged. Workflow definitions already include tests, Ruff, compilation,
hassfest and HACS; no obvious workflow blocker was found. Validation of the new
commit in CI remains required before tagging, rather than a blocker to the
user's review/commit/push.

Suggested v0.1.1 release notes:

- Show Housegard Luma GW650 as the gateway's commercial model without renaming
  the configured gateway.
- Retain WS2GW-R technical metadata in diagnostics and documentation.
- Document OEM evidence and compatibility limits for Heiman, Gardia and LINKD;
  only Housegard Luma is tested/supported.
- Existing protocol behavior, command bytes, alarm/connectivity state and
  diagnostic history remain unchanged.
