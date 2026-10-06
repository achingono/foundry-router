# Native/PDF risks

| ID | Risk | Mitigation | Status |
| --- | --- | --- | --- |
| N1 | Wrong native thinking/cache usage settlement | Disabled-thinking profile, explicit total-inclusion validation and retained usage tests | Review pending |
| N2 | Native SSE EOF falsely completed | Require observed valid finish and clean bounded EOF; actual client fixtures | Review pending |
| N3 | Dropped native signatures | Fail closed until reviewed sealed carrier | Open full-plan gate |
| N4 | PDF parser adversarial CPU/memory/cycles | Resource-isolated worker, input/object/page caps, async bounded parent deadline | Design must be finalized |
| N5 | PDF estimate misses text or page cost | Explicit per-page/text upper bound and token-pricing before enablement | Open |
| N6 | Worker startup/repeated decode blocks intake | Async pre-admission preparation once, bounded worker concurrency/internal context | Design must be finalized |
