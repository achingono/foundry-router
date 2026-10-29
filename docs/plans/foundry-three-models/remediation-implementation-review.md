# Independent MAI remediation implementation review

Historical review: pending execution statements below describe the state at review. The scoped rollout subsequently passed; see [final production evidence](production-evidence.md).

**Verdict: Approved for the scoped remediation implementation.** No Critical or Major findings. Exact replacement handoff remains separately gated.

Reviewer: independent `credit_plan_review` / `gpt-6-astra`; authored neither remediation plan nor implementation. Applied the contextual deep-review prompt to the actual adapter, inspector, worker, lease, MAI intake and tests/docs changes against [approved amendment](remediation-plan-review.md). No source edits or live provider calls performed.

## Contextual conclusions

MAI envelope metadata is ignored only within the already bounded JSON transport; exact one-image item shape, canonical base64, byte cap and digest checks remain. Unverified provider usage is not projected or used to zero the fixed local debit.

The new inspector keyword defaults to false and requires an exact boolean. In enabled mode the existing CRC/container traversal permits one nonempty caBX up to 65,536 bytes only after valid IHDR and before any IDAT bytes. All prior raster, decompression, file-size and chunk-count limits remain. Original bytes are never normalized or stripped, preserving the complete-file digest. Opaque provenance is neither parsed nor authenticated.

The lease validates the server-owned flag before acquiring capacity, then supplies the one recognized worker argument. Unknown or duplicated arguments are rejected by the worker. Existing subprocess isolation, resource limits, bounded stdout and request-owned cleanup remain intact. MAI alone requests the enabled profile; default Google callers and startup gates remain unchanged. No public request/environment switch can select it.

Fixed image accounting, cancellation/lease ownership and no-replay policy remain as previously reviewed. The source amendment does not modify text protocols, pricing, allowances or Table schema.

## Verification and suggestion

Independently ran affected adapter/PNG/lease tests: **99 passed, 1 skipped**. Independently checked exact 64KiB caBX acceptance and caBX rejection after a one-byte first IDAT carrying a partial zlib header. Coordinator reports full **2,867 passed, 90.41% coverage**, Ruff lint/format and mypy (76 sources) passed. Final Linux/amd64 built-image worker/profile evidence passed, as recorded below. SonarQube script remains absent; no successful scan is claimed.

**Suggestion — canonical API/configuration text:** Earlier wording says MAI has no usage receipt, but the measured native envelope includes usage with unverified billing semantics. Static analysis cannot catch this external-evidence discrepancy. Update wording to say unverified provider usage is not interpreted as billable token usage, rather than asserting its absence. Disposition: resolved; canonical API/configuration wording now describes unverified billing semantics rather than absent usage.

Production replacement must independently bind the immutable candidate, MAI-profile acceptance helper, fresh drained balances, the separate USD1 diagnostic liability exactly once, and one new MAI acceptance slot. Keep the original failed image debit and three prior text receipts. This review does not approve the draft replacement driver or public reopening.


Reviewed source manifest SHA-256: `fb75cd33aee1387f60c6e766d47b6a2efa81a993cd4b0c575b3f26d88774eb96`. Manifest entries:

- src/foundry_router/api/adapters/azure_mai.py: `182cedce7e9d52abfbd96462d6ada697ee733164a2047cfc7f4761f0ed180b6f`.
- src/foundry_router/api/google_output_png.py: `44150c29d3dbadd68685aba5f76127a5ff5fa0f3b00c9b002788fde0d4a83ae8`.
- src/foundry_router/api/google_output_work.py: `5ce5be068e1c4daf443a3e66efd49c23d558683c3b8b1353bf006de65593fe9d`.
- src/foundry_router/api/google_output_png_worker.py: `02bf99c3d9338a4a1ce6021254541db6e65eb9088341bc4e6cc24447dbf08603`.
- src/foundry_router/api/routes/openai.py: `9f97fed00c53f36c7aabd05c080e9a73d05a88713a4d04f933a84a988e4a04f5`.


## Final independent gate review

Reviewed [remediation verification](remediation-verification.md): full 2,867 passed / 3 skipped / 19 deselected, 90.41% coverage; final focused/static checks passed. Final `foundry-router:mai-compat` image health and readiness were HTTP200, all checks true. Independent verifier ran Linux x86_64 worker probes proving complete-byte/digest preservation with the MAI profile, default-profile caBX rejection and unknown-flag exit2; Docker used architecture translation on the ARM64 host. Temporary container cleanup completed. Relative links and whitespace/credential scans passed. The stale plan checklist identified by verifier has been updated to distinguish completed local gates from pending replacement handoff/live acceptance.

No unresolved Critical or Major findings or local implementation gates remain. This approval does not itself approve the exact replacement driver, liability handoff, live image acceptance or public ingress restoration.
