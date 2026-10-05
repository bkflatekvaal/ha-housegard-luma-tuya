# Changelog

## 0.1.1

- Present the gateway as Housegard / Luma GW650 in Home Assistant, preserving
  the user's configured name. Retain WS2GW-R as the technical Tuya/OEM model in
  diagnostics and documentation.
- Clarify tested hardware and document evidence for possible Heiman, Gardia,
  and LINKD OEM variants without claiming compatibility or adding brand support.
- Keep the existing verified features, command bytes, connectivity, and normal
  diagnostic history behavior unchanged.

## 0.1.0

- Redact name-bearing raw payloads and gateway identifiers from downloaded
  diagnostics while retaining framing, state, freshness, and classifications.
- Add English and Norwegian entity names through Home Assistant translation
  keys, and complete the duplicate-gateway config-flow abort message.
- Close gateway resources on failed/cancelled setup, tolerate unloaded Tuya
  entries in gateway selection, and report explicit Refresh command failures.
- Document completed automatic Online/Offline live verification and current
  v1 scope; remove the RSSI/Last seen history exclusion recommendation.

## 0.0.2

Initial public release preparation.

- Discover Luma smoke alarms, heat alarms, and RC350 remotes through the existing
  Home Assistant Tuya integration.
- Expose alarm, tamper, connectivity, battery, raw RSSI, last-seen, and inventory
  count entities with persistent gateway-local identities.
- Provide per-alarm Locate and gateway Refresh devices, Network Test, and Sound
  Test buttons.
- Recognize incoming Test/Locate/Hush operation vocabulary, including the newer
  Locate spelling, without embedded capture names or identifiers. Outbound
  RC350 group commands remain unavailable.
- Bundle Housegard logo and icon assets.
- Add public regression tests and GitHub validation workflows. Private evidence
  remains excluded from Git.
