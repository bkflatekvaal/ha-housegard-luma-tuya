# Release preparation

The export contains runtime files, translations, a public README, synthetic tests,
HACS metadata and a defensive `.gitignore`. Production Python files are unchanged.

Before the first public release:

1. Choose an open-source license. No license grant has been invented; add the
   chosen LICENSE before inviting redistribution.
2. The manifest uses the requested repository
   `bkflatekvaal/ha-housegard-luma-tuya` and owner `@bkflatekvaal`. Confirm the
   repository exists and the documentation/issues URLs resolve before release.
3. Review the tested Home Assistant version and compatibility policy. Keep the
   manifest version aligned with release tags; the copied version remains 0.0.2.
4. Add repository description/topics and enable issues. Arrange an appropriate
   integration brand icon without using unlicensed artwork.
5. Run the public checks, HACS validation and Home Assistant hassfest against the
   final repository configuration. Those publishing validators have not run here.
6. Publish a GitHub release. A HACS custom repository and inclusion in the default
   HACS catalog are separate steps; this export does not claim catalog acceptance.

Authoritative requirements:
- https://www.hacs.dev/docs/publish/integration/
- https://hacs.dev/docs/publish/start/
- https://hacs.dev/docs/publish/include/

## Evidence handling

Keep the private evidence archive outside this Git checkout. It preserves exact
captures, names, historical notes and the complete offline suite. Do not commit
it, attach it to a release, or upload it in an issue. `.gitignore` does not protect
already tracked files or files included by another archive/upload tool.

Public replacements must be explicitly labeled synthetic. Do not edit original
capture bytes and then describe the replacements as exact evidence. The retained
RC350 runtime signatures use a generic remote label and protocol-event suffixes,
not factory serials; changing them would change existing classification behavior.

No live HA settings, credentials, databases, logs, backups, `.storage`, local keys,
MAC addresses, factory serials, UUIDs or user location data were copied. Only the
integration and its test/documentation trees were considered for export.
