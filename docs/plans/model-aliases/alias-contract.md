# Planned Alias Contract

## Three Model Identities

| Identity | Example | Responsibility |
| --- | --- | --- |
| Requested model | `codex-auto-review` | Client catalog identity and diagnostic context |
| Resolved canonical model | `gpt-6.1-sol` | Configured pool, policy, estimates/prices, admission and settlement |
| Provider deployment/model | Selected backend's configured `deployment` | Existing backend URL/body mapping; may differ from the canonical name |

Model aliases are distinct from backend aliases in shared credit accounting. They reference a
model pool, never a credit group, endpoint or provider deployment. Multiple aliases create no
extra capacity or account identity.

## Configuration and Resolution

Add `model_aliases_json` with environment name `FOUNDRY_MODEL_ALIASES_JSON`, default `"{}"`, and
derived `model_aliases: dict[str, str]` to Settings. Keep `settings.models` exclusively canonical;
do not expand aliases into copied pools or prices.

- Parse an object of strings with duplicate-key rejection. Reject null/array/nested/non-string
  values, blank names, surrounding whitespace and control characters.
- Names are exact case-sensitive IDs; no Unicode normalization, lowercasing or trimming. Cap new
  alias names/targets at 256 UTF-8 bytes, entries at 1,024 and raw alias JSON at 256 KiB.
- Alias keys must not collide with canonical model IDs. Targets must exist in `settings.models`.
  Reject self references, alias-to-alias targets, cycles and missing targets; one-hop lookup needs
  no recursive traversal. Unrelated backend IDs are not valid targets.
- Reject prices keyed by declared aliases; canonical prices are inherited. Preserve unrelated
  legacy pricing-key acceptance and existing target-pricing readiness behavior.
- No built-in Codex prefix or default target. Unconfigured hidden/custom names remain 404.

Use a small pure config/catalog helper (for example `config/model_aliases.py`) returning immutable
`requested_model`, `resolved_model`, `is_alias`. Resolve once from captured Settings after auth/
body validation and before model-not-found checks in both inference routes. Invalid configuration
fails load; an unknown request name returns existing `model_not_found` without reservation/egress.

Preserve the original request; make one shallow copy changing only top-level `model` to the
canonical name, and never mutate shared nested values. Pass the canonical name to routing,
estimation and settlement; retain identity context separately for diagnostics. Failover never
re-resolves the alias. Streaming closures capture canonical identity and pricing/Settings rather
than looking up a mutable alias at completion. No hot reload is introduced; configuration changes
use the existing revision/restart and drain procedure.

## Request and Response Behavior

The backend client retains its provider mapping: Azure Responses sends the selected deployment
in body `model` on its v1 route; Azure embeddings uses its deployment-scoped versioned path and
the resolved canonical body; Google applies existing model substitution. Every backend attempt
starts from the canonical request. Alias strings cannot choose URLs or credentials outside normal
pool selection.

Preserve instructions, input, tools/tool choice, output schema, reasoning settings, metadata,
stream flags and all non-model fields exactly as parsed. Do not translate reviewer prompts,
strip unsupported fields, alter review output or force an approval. A post-alias 400/schema error
is a separate provider compatibility issue, not permission to weaken a request or choose another
model family silently.

Leave upstream JSON bodies and SSE bytes untouched, including their reported `model`. Document
that accepted alias identity may differ from the provider's response model. Do not parse/rewrite
SSE just to echo aliases. Test the intended client against this policy. The planned Google adapter
may synthesize public model fields from requested identity while accounting remains canonical;
that is its separate protocol contract, not part of this alias-only change.

## Policy and Accounting Inheritance

Alias traffic inherits backend weights, capabilities, health, quota groups, credit groups, metering,
prices and retry policy from the target. Never duplicate reservations, prices, readiness checks,
balance gauges or quotas for aliases. Missing target prices/credit remain the existing readiness/
request-time failures; absence of an alias price never means free or unlimited capacity.

Non-streaming usage, streaming terminal usage, failures, failover and cancellation settle using
the captured canonical identity. Provider-reported `model` and client correlation IDs never choose
billing ownership. Free/metered behavior and memory/Table account keys stay unchanged.

Future capability and bound-history validation must inspect the resolved pool before filtering
candidates. Alternate aliases cannot bypass target restrictions. Future signed state binds the
resolved target as well as requested identity/configuration, so alias retargeting cannot move
signed history elsewhere. These are later integration requirements, not new signature code here.

## Catalog, Readiness and Telemetry

`GET /openai/v1/models` lists each canonical name and alias once, using normal model objects and
`owned_by: "foundry-router"`. Preserve canonical ordering and append aliases deterministically.
All configured aliases are visible to authenticated clients; "hidden" describes an upstream/client
name, not access control or concealment. Add no backend/target fields to public model objects.
The admin-only status endpoint adds a separate `model_aliases` map.

Readiness continues checking unique canonical pools/accounts with no duplicate prices or new
deployment probes. A listed alias represents configuration, not guaranteed availability or
specialized reviewer behavior.

Extend routing summaries with `requested_model`, `resolved_model` and `alias` boolean, keeping
existing `model` canonical. Carry this context through failover and streaming completion without
restoring verbose candidate arrays at INFO. Direct requests have equal names and `alias: false`.
Never log reviewer context, bodies, credentials or outputs.

Existing request/latency/cost metrics count once under canonical `model`, including streaming.
Alias attribution comes from logs and admin mappings. If a mapping metric is needed, use only
the bounded configuration gauge `foundry_router_model_alias_info{alias,target} 1`; no new labels
from rejected arbitrary names and no double counting under alias and canonical identities.

## Deployment and Validation

Add optional nonsecret `modelAliases` object defaulting to `{}` through root/typed Bicep and the
container configuration type/module, serialized into `FOUNDRY_MODEL_ALIASES_JSON`. Existing
defaults remain valid. Runtime validation is authoritative. Create no deployment, vault, identity
or storage resource; `.env.example` defaults to an empty map. Verify rendered env propagation.

For later enablement, recheck the actual canonical pool, provider parameters and readiness. Add
the observed alias first, drain/start the configured revision, verify catalog/admin mapping and
run bounded synthetic normal/streaming calls with usage/settlement checks. Add custom names via
the same path. Roll back by removing aliases in a validated fresh configuration; in-flight requests
settle against their captured target. Production retains its existing memory/one restriction.

Validate approval-client behavior separately using its actual version and synthetic contexts
covering expected allow, deny and malformed/error cases. Keep Codex-generated instructions intact.
HTTP 200 establishes neither reviewer equivalence nor permission for another action. Errors stay
errors; no fail-open approvals. This plan does not alter the approval service or authorize retrying
the previously blocked push.
