# Zen/OpenRouter exit criteria

## Gate checklist

- [x] Independent plan review completed and both Major findings addressed in the plan; see [review](review.md).
- [ ] Both provider literals validated with exact API roots; no arbitrary target/auth forwarding.
- [ ] Zen's explicit stateless-text validator rejects unsupported/foreign fields before Zen admission, including foreign fields alongside valid `input`; accepted bodies change only `model`.
- [ ] Zen operator documentation distinguishes request validation from operator-owned model wire compatibility; no local model-catalog validation claim.
- [ ] OpenRouter uses bounded text translation with the actual provider adapter; routing/plugin/attribution extras never accepted or forwarded.
- [ ] Mixed pools/aliases and quota/credit separation preserved; operation filtering verified.
- [ ] No post-output retries; ambiguous dispatch/cancellation settlement verified for both providers.
- [ ] For both providers and stream modes, `retry_attempts > 1` still makes one dispatch per backend; only 429 permits fresh failover admission, with both quota attempts counted and rejected-attempt credit refunded.
- [ ] Known usage/full-estimate settlement, terminal auth cooldown, cancellation at each ownership boundary, upstream closure and zero outstanding reservations verified.
- [ ] Existing Azure behavior and Google/generic oracles and suites unchanged and passing.
- [ ] Full tests/coverage >= 80%, Ruff/mypy, Docker, deep review, links and diff checks pass.
- [ ] Canonical documentation/traceability updated and included in the phase-transition commit.

Live upstream support is not established by the local implementation gate.
