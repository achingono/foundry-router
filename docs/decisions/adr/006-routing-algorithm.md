# ADR-006: Explainable Credit-Aware Routing Algorithm

## Status
Accepted

## Context
The router must make routing decisions that:
- Maximize utilization across backends before credit cycles end
- Never intentionally cross safety reserves
- Consider both quota (TPM/RPM) and credit (dollar allowance)
- Are explainable (not ML-based black box)
- Support weighted selection with failover

## Decision
Implement a **deterministic scoring function** with the following components:

### Scoring Components (0.0 to 1.0 each)
1. **Availability Score**: 1.0 if ACTIVE, 0.5 if CONSERVATION, 0.0 if PROTECTED/COOLDOWN/DISABLED
2. **Quota Health**: Based on recent 429 rate and TPM utilization (1.0 = healthy, 0.0 = exhausted)
3. **Credit Health**: `min(1.0, spendable_credit / estimated_request_cost)` capped at 1.0
4. **Cycle Urgency**: Increases as `projected_unused_credit / remaining_credit` grows near cycle end
5. **Error Health**: Decreases with recent 5xx rate (1.0 = no errors)

### Composite Score
```
score = (w1 * availability) + (w2 * quota) + (w3 * credit) + (w4 * urgency) + (w5 * error_health)
```
Default weights: `[0.3, 0.2, 0.2, 0.2, 0.1]` (configurable)

### Selection Process
1. Identify candidate backends for the requested model
2. Filter out DISABLED and (if alternatives exist) COOLDOWN backends
3. Calculate score for each candidate
4. Select highest score; tie-break with weighted round-robin
4. Reserve estimated cost before dispatch
5. On transient failure (429/5xx), failover to next highest score (max 1 failover)
6. Never retry/failover after streaming starts

### State Transitions
- ACTIVE → CONSERVATION: when `projected_unused_credit > threshold` AND `days_remaining < threshold`
- ACTIVE/CONSERVATION → PROTECTED: when `spendable_credit <= 0`
- Any → QUOTA_COOLDOWN: on 429 response
- Any → ERROR_COOLDOWN: on N consecutive 5xx
- COOLDOWN → ACTIVE: after cooldown period expires

## Consequences

### Positive
- Fully explainable: every decision logs model, backend, all scores, reason
- Deterministic: same inputs → same decision (testable)
- Safety-first: reserves enforced before dispatch
- Utilization-aware: urgency increases near cycle end to reduce waste
- Separates quota and credit concerns correctly

### Negative
- Requires tuning weights and thresholds (start with conservative defaults)
- Cycle urgency calculation needs accurate daily burn estimates
- More complex than round-robin (but required by requirements)

### Neutral
- Algorithm is pure function (easy to unit test with property-based tests)
- Can be evolved without changing interface

## Alternatives Considered
- **Round-robin**: Ignores credit, quota, safety - rejected
- **Least-loaded**: Doesn't consider credit cycles or reserves
- **ML-based predictor**: Not explainable, requires training data, overkill
- **Pure cost-minimization**: Could starve backends with higher cost but available credit

## Related
- ADR-005: State management (credit balances, reservations)
- ADR-007: Cost reconciliation (authoritative data feeds scoring)

## References
- Routing policy spec: `docs/features/routing.md`
- Credit cycle calculations: `docs/features/routing.md#credit-and-cycle-policy`