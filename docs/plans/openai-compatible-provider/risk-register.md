# Provider risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Generic falls through Azure transport | Wrong URL/wire/accounting | Explicit translated dispatch and API regressions | Mitigated locally |
| R2 | Root/auth ambiguity | Wrong target or credential exposure | Exact root/Bearer contract and confinement tests | Mitigated locally |
| R3 | Google capability assumptions leak | Unsupported shapes or coupling | Independent context and explicit feature rejection | Mitigated locally |
| R4 | Shared forwarding changes Google behavior | SSE/settlement regressions | Unchanged oracle and lifecycle suites | Mitigated locally |
| R5 | Ambiguous 5xx repeats generation | Double spend/output | Single-shot attempts and conservative settlement | Mitigated locally |
| R6 | Local test interpreted as universal support | Unsafe rollout | Exact upstream/model live gates | Open: live gate |
