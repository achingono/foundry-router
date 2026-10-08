# Canonical projection snapshot decoding

**Planned**, 2026-10-06. Independent review required before runtime changes.

The isolated worker-retention repeats pass billing/cleanup and the 128 MiB RSS bound but fail
the 50 ms loop bound: preencoded 76.93 ms, full SDK 117.50 ms. Worker lifetime repair does not
close the resource gate. The signed projection repeatedly runs the bounded external JSON scanner
on freshly canonicalized, already validated local JSON solely to create an owned snapshot.

Propose a feature-local change to `google_history.project_item`: retain structural validation,
normalization and `canonical_bytes(projected)` unchanged; decode its returned bytes using
`json.loads` to obtain the owned snapshot instead of calling `load_bounded_json` again. The
canonical helper already performs eager depth/node/key/finite/UTF-8/size validation, with strict
encoded-output validation for any non-exact builtin tree. External request and sealed-token
parsers remain unchanged. No snapshot cache, mutable reference retention, digest skip, wire/size
limit changes, routing/finance changes or new capability. A tuple must still become a JSON list;
subclasses still pass canonical helper's fallback before snapshot decoding.

Review proof obligation: current canonical validation must imply the exact scanner limits and
JSON semantics for the projection's 2 MiB budget, including any difference in dictionary-key
node counting, depth, integer/float decoding, duplicate-emitting subclasses and special scalar
subclasses. If this implication does not hold, reject this proposal or identify the additional
local validation required without weakening acceptance. Only optimize local trusted encoding.

Tests should differentially compare old/new projection acceptance and exact values (including
subclasses, tuples, nonfinite, invalid Unicode, size/depth/node edges); prove snapshots do not
retain mutable input children; preserve actual signed client round trips, mutation rejection,
media facts and billing. Run focused/full coverage, lint/format/type/Docker, independent deep
review and isolated current-source resource repeats. Keep all failing artifacts and startup/live/
production gates closed until their own evidence passes.
