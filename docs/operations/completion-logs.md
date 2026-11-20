# Completion console observations

Status: Implemented locally and disabled by default. Azure ingestion, multi-worker completeness, alerts and scale acceptance require environment-specific verification.

Set `FOUNDRY_COMPLETION_LOGS_ENABLED=true` only in a reviewed configuration. The sink emits `foundry_router_completion` schema version 1 with a server-generated event ID, process-instance ID, configured logical model/backend identifiers, HTTP status, finite nonnegative duration and optional `estimated_cost_usd`. Unknown observation pairs become fixed `other`/`none`. Prompts, outputs, request/correlation IDs, headers, credentials, URLs and exception text are excluded. Records are redacted before serialization and do not merge ambient request context. Costs remain local estimates.

Existing metrics sites create observations. Nonstreaming duration starts at routing/admission and ends at response construction; streaming duration starts at forwarding and ends at stream finalization. Failover can record a failed attempt and a later result. Authentication, intake rejection and unobserved exceptions are outside this boundary. Use platform request/status metrics for ingress totals; completion observations do not count every client request or prove downstream delivery.

A single process-owned daemon writes the console stream from a fixed 256-record queue with a 2,048-byte serialized-record bound. A blocked writer holds at most one extra record. Request code performs no console writes, waits or retries; overflow drops observations. Authenticated `/admin/status.telemetry.completion_logs` reports submitted, written, failed, dropped, invalid, observation_errors and pending counters. Process identity survives metric resets and repeated application lifespans; a new process/fork has a fresh identity. Closing gives pending writes at most one second of asynchronous grace; final writes can be lost at process exit. Console success does not prove destination ingestion.

## Destination acceptance

Use an existing destination with verified access and retention. Confirm its table and worker column names; replace placeholders with privately observed values and a bounded exercise window.

```kusto
let start = datetime(<exercise-start-UTC>);
let finish = datetime(<exercise-finish-UTC>);
let Observations = ContainerAppConsoleLogs_CL
| where TimeGenerated between (start .. finish + 10m)
| where ContainerAppName_s == "<observed-app-name>"
| extend e = parse_json(Log_s)
| where tostring(e.event) == "foundry_router_completion" and toint(e.schema_version) == 1
| extend event_id=tostring(e.event_id), process_id=tostring(e.process_instance_id),
         model=tostring(e.model), backend=tostring(e.backend),
         status=toint(e.status_code), duration=todouble(e.duration_seconds),
         cost=todouble(e.estimated_cost_usd)
| where strlen(event_id)==32 and strlen(process_id)==32
| where status between (100 .. 599) and isfinite(duration) and duration >= 0
| where not(bag_has_key(e,"estimated_cost_usd")) or (isfinite(cost) and cost >= 0)
| summarize arg_min(TimeGenerated, *) by event_id;
Observations
| summarize observations=count(), errors=countif(status >= 400),
            duration_p95=percentile(duration,95), estimated_cost_usd=sum(cost)
  by process_id, ContainerGroupName_s, model, backend, status
```

Verify finite-number filtering and deduplication against the actual destination schema. Compare known observation-site calls, including failover attempts, with deduplicated event sets, statuses, cost estimates and per-process written deltas. Allow a bounded ingestion delay; missing/unexpected observations, identity mismatches, drops, failures, invalid counters or unknown ingestion fail completeness acceptance. Repeat across actual workers and a targeted restart while preserving canonical Table finance.

## Alerts and response

Before scale-out, independently review alerts for platform request errors, completion errors/duration, restarts and resource pressure using measured normal levels and exercise thresholds. Validate firing and resolution with bounded synthetic failures. Check local drop/failure/pending counters separately: console alerts cannot detect console loss, and silence is normal for an idle application.

Investigate readiness and platform availability, then process identities, local counters, ingestion delay and schema. Restore an accepted single-replica configuration after failed scale acceptance. Never sum canonical Table balances/debit counters across workers or treat one worker's authenticated metrics as an aggregate.
