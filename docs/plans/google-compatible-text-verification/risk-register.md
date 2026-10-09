# Compatibility verification risks

| Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- |
| Native success mistaken for compatible access | Unsupported rollout | Separate exact-surface operation evidence | Open |
| Retrying ambiguous call | Unbounded quota spend | Unique deterministic cases, durable retained debit, no retries | Planned |
| Provider-default thinking | Unknown thought cost/accounting | Output/token caps; absent metadata remains unknown | Open |
| Secret/output disclosure | Sensitive evidence | In-memory keys, quiet logs, numeric/boolean evidence only | Planned |
| Buffering verification stream | Overstated latency/cancel proof | Explicitly exclude those gates; bounded buffer and deadline | Planned |
