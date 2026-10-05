# V1 release audit — 2026-10-05

Historical v0.1.0 audit. The subsequent v0.1.1 release preparation changes the
primary gateway model to **Luma GW650**, retaining **WS2GW-R** as technical Tuya
metadata, and uses release tag **v0.1.1**. See the current README/changelog and
[OEM investigation](oem-platform-investigation-2026-10-05.md); version/model
statements below describe the original audit rather than current release metadata.

Core v1 functionality is considered complete, based on the user's live
verification and offline regression coverage. The public integration is ready
for release review after the existing hassfest/HACS CI gates pass. No release,
tag, live command, or live test was performed by this audit. Following the audit,
the release version was bumped to 0.1.0; “v1” describes feature scope.

## Findings and disposition

| Classification | Finding | Disposition |
| --- | --- | --- |
| RELEASE BLOCKER | Downloaded diagnostics included gateway identity and reversible name/serial-bearing packets despite redacting parsed names. | Fixed: export excludes raw Base64/hex, decoded text, gateway IDs and opaque inventory headers. Safe framing, classification, state, timestamps and gateway model remain. Internal captures and runtime processing are unchanged. |
| SHOULD FIX | Entity names bypassed localization; duplicate-gateway abort text was absent. | Fixed: translation keys for all entities, complete English and existing Norwegian catalogs, matching `strings.json` and English catalog. English labels and unique IDs are retained. |
| SHOULD FIX | Unloaded Tuya entries may have no `runtime_data`, breaking gateway selection. | Fixed: skip missing runtime/manager. Tuya owns authentication and reauthentication; Luma has no independent credentials or reauth flow. |
| SHOULD FIX | Failed/cancelled setup detached listeners but did not close the gateway runtime. | Fixed: register `async_close` before restoration; HA invokes it on failed/cancelled setup as well as unload. Normal unload still flushes storage and closes captures; closing twice is safe. |
| SHOULD FIX | Gateway buttons did not subscribe to availability updates; Refresh failures returned silently. | Fixed: subscribe through the gateway dispatcher with entity cleanup; Refresh checks transport availability and reports send failures without transport details. In-flight/cooldown guards remain. |
| SHOULD FIX | An excessively long numeric `dpId` could raise during the MQ callback. | Fixed: reject conversion failure. Explicit DP codes must be strings. Verified packet parsing is unchanged. |
| SHOULD FIX | Documentation still recommended RSSI/Last seen exclusions and listed incomplete connectivity verification. | Fixed: removed exclusions; both transitions are DONE and upstream offline latency is explained. |
| SHOULD FIX | A full Tuya reload/reauthentication can replace its runtime manager while Luma retains the old manager. | Documented workaround: reload Luma afterward. Automatic manager rebinding is deferred because it would change connectivity runtime behavior, outside this task's preservation constraint. Normal MQ reconnect/replacement within the existing manager is already supported. |
| NICE TO HAVE | No full HA runtime tests are included; public HA-facing tests use interface doubles. | Keep as a future testing improvement. Archived tests also use doubles and are not evidence of the new export/localization behavior in a running HA instance. |
| NICE TO HAVE | Action error messages remain safe English text. | Further exception localization can follow; config and entity names are localized. |
| NICE TO HAVE | Screenshots and issue templates are absent. | Optional improvements; installation and issue-reporting instructions already exist. |

## Audit coverage

- **Entry lifecycle:** setup waits for the existing Tuya runtime, restores Store
  state, attaches three passive MQ listeners and one connection-following timer,
  forwards platforms, then sends the established inventory query. Successful
  unload closes captures, cancels inventory timeout, flushes dirty Store state,
  and HA removes dispatcher/timer callbacks. Tests cover failure, cancellation,
  two entries, reload without duplicate listeners and complete cleanup. Normal
  MQ replacement follows the existing 30-second connection check. A separate
  manual Tuya integration reload can replace the entire manager, which Luma
  holds from setup; reload Luma after such a Tuya reload. Automatic handling of
  whole-manager replacement is a deferred SHOULD FIX, not changed in this polish task.
- **Entity lifecycle:** unique IDs remain gateway ID + inventory index + entity
  key. Device identifiers remain stable and gateway-local. Parent association
  resolves the existing Tuya device with its config entry and uses
  `via_device_id`, avoiding the deprecated `via_device` argument. Dynamic
  discovery adds each index once; partial inventory retains existing devices.
  Store records reconcile with inventory rather than being removed. Unknown
  types receive the generic model and no speculative alarm/control entities.
- **Metadata:** Smoke/Heat/Tamper/Online use SMOKE/HEAT/TAMPER/CONNECTIVITY device
  classes. Battery is diagnostic BATTERY with `%`; RSSI is diagnostic and
  intentionally unitless with no guessed SIGNAL_STRENGTH class. Last seen is a
  diagnostic TIMESTAMP. Sensors have no state class. Gateway counts/buttons and
  Online are diagnostic; Locate is an ordinary action. Existing icons, entity
  enablement defaults, history eligibility and availability semantics remain.
  RSSI/Last seen have no Recorder exclusion metadata.
- **Buttons:** explicit presses use the existing Tuya manager/executor with one
  command per accepted action, selected gateway only, and inventory index for
  Locate. Exceptions/rejected commands are handled without leaking transport
  details. Refresh retains its existing cooldown and in-flight behavior.
  Setup/reload sends one `02 07` inventory query, intentionally preserved;
  it never sends Locate, Network Test, or Sound Test automatically.
- **Restore/freshness:** parsed battery/RSSI/Last seen and alarm states use an
  allowlisted Store schema. Restored Online is unknown, not stale true; cached
  inventory does not make it fresh. Inventory updates valid telemetry and
  connectivity without clearing alarms or advancing Last seen. Persisted active
  alarms require an explicit verified clear report. Individual reports preserve
  current connectivity evidence and are not a heartbeat. No timeout or Last seen
  age inference was added.
- **Logging/errors:** routine capture/connection activity is quiet; unknown
  Smoke/Heat values log at debug. Storage and inventory send failures use
  actionable warnings without raw exceptions. Malformed framing/Base64/UTF-16
  fails conservatively; unknown connectivity is unknown. The audit did not add
  speculative recovery or protocol interpretation.
- **Privacy:** diagnostics never traverse the Tuya device/account object or
  config-entry data. Local keys, tokens, credentials, account IDs, IPs, MACs,
  UUIDs, factory serials and location are not exported. Registry identifiers
  still use gateway IDs internally, as required for stable identity; no normal
  entity exposes these as a value. Public fixtures use synthetic names/IDs and
  generated packets. `PRIVATE/` is ignored and has no tracked files; captures,
  logs, `.storage`, configuration and secrets are ignored. Existing branding
  assets and their ownership notice were retained; no assets were added.
- **Distribution:** manifest declares `hub`, `cloud_push`, config flow, Tuya
  dependency, codeowner, documentation/issue URLs and version. `hacs.json`
  declares minimum HA 2026.9.4. No direct cloud SDK dependency is added. License,
  manual/HACS install instructions, version strategy and reporting guidance are
  present. CI already runs public tests, Ruff, compilation, hassfest and HACS.

Entity localization follows the [HA entity translation guidance](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/entity-translations/).
Failed setup cleanup follows [HA 2026.9.4 config-entry lifecycle](https://github.com/home-assistant/core/blob/2026.9.4/homeassistant/config_entries.py).

## Verified scope and checklist corrections

Both automatic Online -> Offline and Offline -> Online transitions without
manual Refresh are **VERIFIED / DONE**, per the user. HA follows Luma/Tuya;
offline recognition can be slow upstream. No custom HA supervision was added.

Discovery, inventory continuation DPs, active Refresh, Store, gateway isolation,
detector telemetry, tamper/recovery, Smoke/Heat trigger/restoration and distinction
from physical/self tests are complete. The exact real Heat Triggered -> Alarm
Restored sequence and Smoke/Heat Locate are live verified. Gateway Network Test
and Sound Test are implemented and live verified. RC350 incoming Test, Locate
and Hush/Silence are verified; there is no separate HA Test event entity.

The requested checklist mentioned **Unknown devices**, but the current public
implementation intentionally exposes only Devices, Online devices and Offline
devices. Offline includes inventory records not known to be online. Setup removes
the obsolete Unknown devices entity for this entry. The audit preserves that
existing design rather than inventing a fourth count or changing count semantics.

Gateway metadata is implemented and tested as Housegard / WS2GW-R, using Tuya
Device Details evidence: model `WS2GW-R`, product name `Wireless Interlink
Gateway`, product ID `s3x3xmgbeohtvm40`, category `mal`. Generic models are
intentional: `02` Luma Smoke Alarm, `12` Luma Heat Alarm, `0A` Luma RC350,
unknown Luma subdevice. Exact SA750/HA450-style commercial names are not inferred.

## Future protocol work — non-blocking

- RC350 outbound group Test/Locate/Hush: not implemented; do not guess commands.
- Robust routing of Operation-log-only remote actions across multiple remotes
  and re-pairing remains unresolved. Online event matching retains its existing
  exact unique gateway-local name/type rules.
- Network Test result observations `07 07 FF 03 0C 01 00` (12 online / 1 offline)
  and `07 07 FF 03 0D 00 00` (13 online / 0 offline) strongly support counts,
  but final-byte/formal completion semantics remain unresolved. Production
  counts/connectivity continue to use inventory and supported Online events.
- Exact commercial Smoke/Heat model is not established by current evidence.

Verified command bytes remain Network Test `07 07 FF 03 3C`, Sound Test
`07 07 FF 02`, Locate `07 07 <inventory index> 04`, inventory query `02 07`.
`parser.py`, `registry.py`, `operation_log.py`, `storage.py` and `const.py` are
unchanged by this audit.

## Validation and release gates

| Check | Result |
| --- | --- |
| Current public suite | 73 passed; includes 24 added release regression cases |
| Archived private suite | 556 passed with Python `-X utf8`, run independently from `PRIVATE/` |
| Ruff lint | Passed for current production/public tests |
| Ruff format check | Passed, 17 files |
| Python compilation | Passed for current production/public tests |
| Archived Ruff/format/compilation | Passed; 69 archived Python files formatted |
| Local manifest/catalog checks | Passed: metadata/baseline/version consistency, JSON parsing and translation key coverage |
| hassfest | Unavailable locally: `python -m script.hassfest --integration-path custom_components/housegard_luma` fails because `script` is not installed |
| HACS validation | Unavailable locally: no HACS validator or Docker; existing `hacs/action` CI job is the release gate |

The private suite targets the preserved archived source, not the changed public
package. Its historical notes/TODOs are kept intact as evidence and are superseded
by this report/README for current release status. Neither test suite connects to
Home Assistant or Tuya. Local manifest checks do not substitute for hassfest/HACS.

Before tagging, require successful hassfest/HACS CI for the final commit, confirm
HACS-required repository topics, align tag `v0.1.0` with the manifest/changelog,
and inspect the release contents for
private evidence. Review translated labels and diagnostic export presentation
in Home Assistant during an ordinary installation/reload; no additional
protocol-command live validation is required by this audit.

## Exact files changed

Production changes under `custom_components/housegard_luma/`:

- `__init__.py`: close runtime on failed/cancelled setup.
- `config_flow.py`: tolerate unloaded/missing Tuya runtime.
- `capture.py`: guard malformed DP metadata/integer conversion.
- `diagnostics.py`: safe export and gateway model.
- `button.py`: translations, availability updates and explicit Refresh errors.
- `binary_sensor.py`, `sensor.py`: translation keys; no value/history changes.
- `strings.json`, `translations/en.json`, `translations/nb.json`: complete labels
  and duplicate-gateway abort text.
- `manifest.json`: explicitly declare hub integration type; subsequent release
  version bump to 0.1.0.

Repository/documentation/tests:

- `README.md`: current scope, completed connectivity verification, privacy,
  Tuya reload workaround and release guidance; remove history exclusions.
- `CHANGELOG.md`: unreleased polish changes.
- `docs/release-audit-2026-10-05.md`: findings, scope, evidence and validation limits.
- `tests/housegard_luma/test_public.py`: identify translated entities by key.
- `tests/housegard_luma/test_release_audit.py`: 24 new synthetic regression cases.

No private evidence or archived source was edited. No dependency, command-byte,
alarm parsing, count semantics or connectivity production change was made.
