# Deep Review Remediation Plan

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Objective
Remediate the Critical/Major findings from the 11-phase deep review without changing owning boundaries: release orphaned credit reservations on failover, wire backend/model topology into Container Apps, correct Google AI Studio payload/endpoint mapping, harden test collection without the optional `azure` extra, fix smoke-test auth, and harden `finalize_request` partition lookup. Multi-replica shared state remains Partially implemented; production stays memory-backed with `maxReplicas: 1` until cut-over gates pass.

## Scope

## In Scope
- `src/foundry_router/routing/__init__.py`: release `first_backend_id` reservation on retryable failover before second selection.
- `src/foundry_router/state/table.py`: `finalize_request(None)` scans `_configured_backend_ids`; reduce `live_snapshot` lock hold over I/O.
- `src/foundry_router/backends/__init__.py`: substitute `config.deployment` into Google payload `model`; map `responses` operation to Google-supported `chat/completions`.
- `infra/main.bicep`: add Key Vault-backed `FOUNDRY_BACKENDS_JSON`, `FOUNDRY_MODELS_JSON`, `FOUNDRY_PRICING_JSON`, cycle-day/allowance/remaining params and env wiring.
- `tests/integration/azurite_fixtures.py` + unit table tests: `pytest.importorskip` guards so collection passes without `azure` extra.
- `scripts/operations/smoke-test.sh` + `deploy.yml`: `--client-key` for authenticated `/openai/v1/models` check.
- `docs/decisions/requirements-traceability.md`: add Phase 11 section as Partially implemented.

## Out of Scope
- Full OpenAI Responses→Chat adapter semantics beyond operation mapping + model substitution.
- Multi-worker metrics aggregation (Planned), two-replica Azure validation (pending).
- Bicep actual secret values (supplied via Key Vault / workflow secrets, never committed).

## Entry Criteria
- Current tree inspected; findings verified against code paths listed above.
- Focused tests runnable via `.venv/bin/python -m pytest`.

## Exit Criteria
- Focused + full unit tests pass without `azure` extra installed in collection path (azure-marked tests skip).
- No `FOUNDRY_BACKENDS_JSON`-missing crash path from template defaults; Bicep builds/lints where tooling available.
- Traceability updated; docs links valid; diff contains no secrets or unverified deployed claims.

## Roles
- Owner: implementation session
- Reviewer: different model/session (deep-review prompt)
- Approver: maintainer
