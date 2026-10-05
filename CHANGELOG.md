# Changelog

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
