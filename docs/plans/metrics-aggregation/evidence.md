# Metrics evidence

**Planned**, 2026-10-08. Six templates copied and canonical metrics/observability,
startup/router references, Docker and existing tests inspected. Current runtime has only
process-local Prometheus counters and no OTel SDK dependency. Runtime implementation has
not started; Independent review initially found cumulative-reset and cardinality gaps; amended local-only
reset/lifetime teardown and explicit series budgets resolved them. Re-review cleared runtime
implementation with no remaining Critical/Major issues. Official pinned SDK/exporter 1.45.1
wheels inspected; transport/reader retry, environment and shutdown behavior require concrete
confinement tests.

Pinned HTTP client inspection found 3xx success and raw reason logging. Independently
reviewed amendment uses the official SDK/export encoder with a confined single-shot
transport and bounded complete/partial/malformed acknowledgement checks. Final amendment
cleared before runtime edits.

## Implementation verification

**Implemented** locally, 2026-10-08. Full suite: 1,711 passed, three platform skips,
17 Docker/Azurite deselections; coverage 89.48%, OTLP module 89.84%. The later API live-proxy
regression passed as part of 18 focused telemetry tests. Ruff and strict mypy passed.
The repository has no conditional SonarQube scan script. Final Docker build and Python 3.12.15 network-disabled app/OTel cumulative/shutdown
smoke passed. Relative links and final whitespace/status/redaction diff checks passed.

- [Unit tests](../../../tests/unit/test_otlp_metrics.py): cumulative per-lifetime identities,
  local reset, exact histograms, single-shot auth/endpoint/environment confinement,
  HTTP/partial/malformed/bounded acknowledgements, series overflow, disabled SDK, slow
  async trickle deadline, constructor/startup failures and API live proxy.
- [Actual subprocess test](../../../tests/integration/test_otlp_processes.py): two workers
  reached autonomous five-second export ticks, then final collection; one restarted worker
  had a new lifetime ID. Duplicate/reversed cumulative samples yielded nine requests,
  $4.50 synthetic estimated cost, nine exclusion entries and matching histogram totals.
  Collector auth and protobuf path were verified on a local receiver; no Azure claim.
- [Independent contextual review](implementation-review.md): deadline and partial-startup
  ownership findings fixed, no remaining Critical/Major findings. Suggested original startup
  error preservation added and tested. Default memory metric singleton preserved after
  full-suite alias tests revealed stale imported references following a failed-startup test.

The official SDK/encoder is pinned to 1.45.1, with optional telemetry dependencies installed
in the Docker runtime. Single-shot httpx transport uses a total async network deadline,
no ambient proxy/auth, TLS verification, 1 MiB request/64 KiB acknowledgement bounds and
safe acceptance categories. Resource/exemplar/env and series budgets are explicit.
Shutdown relies on the periodic reader's serialized final collection without a competing
force flush. Production stays memory/one; collector/network/provider/deployed scale-out
verification remains outstanding.
