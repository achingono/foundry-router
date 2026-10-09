# Multi-worker and multi-replica metrics aggregation

**Implemented** locally, 2026-10-08. Deployed collector acceptance remains unverified. Workstream 5b of the
[routing roadmap](../google-ai-routing-order/index.md). Production remains memory/one.

## Concrete contract

Add opt-in OpenTelemetry metric push using the official Python SDK and OTLP HTTP exporter,
with a configured collector endpoint. Default authenticated Prometheus exposition retains
its current behavior. No new Azure service or infrastructure in this code phase: an actual
collector/backend, authentication and network route are operator-supplied rollout inputs.
File-based Prometheus worker sharing alone cannot aggregate separate Container App replicas.

Every process sends cumulative counters/histograms through its own MeterProvider with a
unique generated `service.instance.id` for each process lifetime, common configured
`service.name`, optional configured replica/revision identifiers and PID. Central collection
preserves those resource identities; downstream sums **rates/increases per instance** for
request/cost/exclusion counters and combines histogram buckets by model/backend. Never sum
repeated cumulative OTLP snapshots as new events. Restart creates a new series identity;
collector/backend retention handles exited instances without local file cleanup.

Implement a metrics-store wrapper which retains the existing local Prometheus store and
records request outcome, request duration histogram with existing explicit bucket boundaries,
estimated cost and combination exclusion counters through SDK instruments. Configure an explicit telemetry series budget (default 2,048, maximum 16,384). Validate
configured model/backend/operation combinations against this budget before startup; arbitrary
backend counts remain supported within the operator-selected finite budget. Use explicit
SDK per-instrument cardinality limits/views if available and reject/drop unexpected labels
to a fixed bounded sentinel. Validate status into a fixed HTTP-status set; no user-supplied
free-form labels. Test overflow behavior and worst-case histogram/export payload bounds.
Labels remain
configured model/backend/status/operation/stream, no prompts/outputs/keys or user request IDs.
Instance IDs belong to OTel resources, never client-provided labels. Alias requests retain
canonical model attribution. Latency is existing request completion/stream duration;
do not claim an independently measured TTFT histogram.

State gauges (credit/quota/health/alias config) stay authenticated local Prometheus/admin
snapshots, not additive OTel counters. Their repeated Table/account/backend views must not
be summed across replicas. Document central `min`/latest grouping for shared credit/quota
and per-instance health grouping if operators scrape them independently. Push only bounded
counter/histogram families in this phase; changing gauge export needs a separate contract.

Configuration includes exporter enabled flag, service name, explicit HTTPS endpoint ending
`/v1/metrics`, externally supplied optional secret authorization header, and bounded export
interval (5–60 seconds) and timeout (1–10 seconds). Reject userinfo/query/fragment, redirect
following and unsafe endpoint routing syntax. Loopback HTTP is test-only injection, not
production config. Never emit exporter auth or full URL in logs/admin/config diagnostics.
Pin `opentelemetry-sdk==1.45.1` and `opentelemetry-exporter-otlp-proto-http==1.45.1`.
SDK/exporter dependencies are optional telemetry extras installed in the Docker runtime so
opt-in works in the shipped image; default imports do not construct exporters or threads.

Startup owns wrapper/provider initialization after configuration and before serving. API
routers use the live metrics proxy so lifespan rebinding reaches already assembled routes.
Enabled startup fails explicitly when dependencies or exporter construction are unavailable.
Explicit config takes precedence over ambient OTEL endpoint/auth/compression settings; the
confined transport disables ambient proxies/netrc/auth and cannot disable TLS verification.
Test hostile environment sentinels without logging their values. Reject enabled startup when
OTEL_SDK_DISABLED=true instead of silently running a disabled meter; construct explicit
Resource (without ambient detectors) and AlwaysOffExemplarFilter so trace/request IDs never
enter exemplars.
SDK export occurs on its periodic reader thread, never waits on provider traffic. Bound
export deadlines/retries through the official exporter; inspect its exact transport behavior
rather than assuming no redirects or bounded retries. Inspection of pinned 1.45.1 found the HTTP client treats 3xx as successful delivery, retries
transient failures and logs transport exception/reason strings. Use the official SDK
MetricExporter interface and official OTLP protobuf encoder with a confined single-shot
HTTP transport rather than inheriting those client semantics. Explicit cumulative temporality,
1 MiB maximum protobuf request, 64 KiB bounded acknowledgement, HTTPS/TLS/no redirects/no
ambient proxy settings and sanitized failure categories define this exporter. No provider
outputs or raw collector errors are logged. Accept HTTP 200 OTLP protobuf acknowledgements
only; an empty body is the valid empty protobuf response. Decode bounded
ExportMetricsServiceResponse and distinguish partial_success.rejected_data_points from full
delivery; malformed protobuf or partial rejection is a failed/partial health category, never
complete acknowledgement. Discard error_message, logging only categories and numeric rejection
counts. Test empty/full/partial/malformed200 and3xx/429/5xx. One failed export retries only at the next
periodic cumulative snapshot; final flush loss remains visible and cannot be fabricated.
Exporter failures cannot alter inference success or financial settlement, but log redacted
error type/category and expose local exporter-health state without claiming delivery.
Wrapper `reset()` resets only the local Prometheus view: cumulative OTel instruments never
reset under the same service.instance.id. Each new lifespan constructs a new provider/resource
lifetime after shutting down the prior wrapper. Test repeated reset and lifespan behavior;
document that local reset is diagnostic, while exported cumulative counters remain monotonic.
Shutdown orders request drain, a single bounded reader flush, provider shutdown, then local
reset. Serialize flush/shutdown so concurrent exports are not started by teardown.
Shutdown flushes and stops the reader using bounded timeout; cancellation must not leak a
background thread or retain secret credentials in detached tasks.

## Verification and central aggregation evidence

Independent review is required before runtime edits. Use SDK in-memory exporters to verify
two independent providers/processes produce separate resource identities, exact request/cost
counts and histogram buckets. Simulate periodic repeated export and restart; aggregate
cumulative streams by metric/resource/attributes/start/end timestamps. A new lifetime
contributes its full first cumulative value; later samples contribute positive differences.
Ignore stale/out-of-order/repeated snapshots, and include delayed delivery and graceful final
flush to prove no duplicate counting or dropped pre-first-export requests.
Run two real subprocess workers against a local test OTLP receiver with synthetic credentials;
drive disjoint observations and verify combined request/cost/exclusion totals and histograms,
then restart one worker and verify continued totals across new lifetime identity. This is
local central aggregation evidence, not deployed Azure collector/provider acceptance.

Test unchanged authenticated Prometheus output, no-export default, no provider hot-path I/O,
auth redaction, endpoint/retry confinement, exporter failure, bounded shutdown and API live
proxy wiring. Full ≥80% coverage, Ruff/mypy, Docker and contextual review are required.
Record exact Python SDK/exporter versions and protocol evidence, update observability,
configuration/security/architecture/traceability, validate links/diff and commit transition.

## Companion documents

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
