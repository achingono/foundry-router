# Operations

Status: Runtime, typed Bicep modules, Table credit/health adapters and local synthetic verification are Implemented. Environment-specific production acceptance remains separate from implementation status.

Use [production maintenance](production-deployment.md) for reviewed deployment and rollback. The automatic production workflow is guarded. An image build or configuration validation does not authorize a live rollout.

Credit and health state support memory or Table configuration. Memory state is process-local and restarts lose its ledger lifetime. Authoritative Table state must be retained across revision changes; never reseed accounts or return to stale memory balances. Before scale-out, verify readiness completeness, identity-only Table access, shared reservations, exact settlement and targeted restart persistence with the configured models. Quota is a separate concept; configure provider limits from verified inputs and validate distributed admission independently.

Optional Azure intake is disabled by default. Accept the entire application lifecycle, concurrent child preparation, Unicode/Base64 expansion, input/output wire boundaries, scratch capacity, cleanup, streaming and provider ingress before enabling larger requests. Keep resource shape and replica limits unchanged until the relevant gates pass. See [configuration](../configuration/index.md#optional-azure-intake-budgets).

Optional [completion console observations](completion-logs.md) and central OTLP aggregation require destination ingestion, loss accounting and multi-worker acceptance. Authenticated process-local metrics do not aggregate replicas. Shared Table account balances and debit counters must not be summed across workers.

Use [observability](observability.md), [shared credit operations](shared-resource-credit.md) and the [infrastructure guide](../../infra/README.md) for feature-specific requirements. Local prices and balances are estimates and never establish authoritative provider credit.
