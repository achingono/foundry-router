# Isolated Ingress Watchdog Evidence

**Review status: Independent design-only review passed; operator approved all stages in principle. Exact infrastructure/execution packets and independent reviews remain required.**

## Evidence Log

| Item | Reference | Notes |
|---|---|---|
| Triggering reviewer finding | [G1 resume evidence](../table-production-autoscaling/g1-ready-finish-resume/evidence.md) | Independent exact packet review rejected the packet because SIGTERM/SIGKILL/system failure may bypass the runner `finally` DENY |
| Existing enforcement path | [G1 resume runner](../../../scripts/quality/table_production_acceptance_resume.py) | DENY is in a Python `finally`; this is not process-crash protection |
| Azure ingress research | [Container Apps ingress](https://learn.microsoft.com/azure/container-apps/ingress-overview) | Official docs describe public/internal ingress and IP restrictions; this does not prove same-environment bypass behavior for the target app |
| Azure ingress-log research | [Container Apps log monitoring](https://learn.microsoft.com/azure/container-apps/log-monitoring) | ACA HTTP logs expose `ResponseCodeDetails` and `UpstreamRequestAttemptCount`; docs say response-code details indicate who set the status. Exact policy-denial values and log completeness still require disposable-app calibration; no 403 fingerprint is assumed |
| Azure job research | [Container Apps jobs](https://learn.microsoft.com/azure/container-apps/jobs) | Jobs support manual, schedule, and event triggers; scheduled execution is not a request-path expiry mechanism |
| Static IP reference | [Public IP addresses](https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-addresses) | Design assumes a stable gateway public endpoint for runner access; private routing and restriction compatibility remain to verify |
| Independent review, first pass | User-provided review feedback | Rejected: durable session replay after restart, origin-side DENY proof, and single paid-call enforcement required |
| Independent review, second pass | Separate code-review agent | Rejected with three Majors: replay ledger deletion protection, renewal bound to runner liveness, and shared-environment bypass evidence |
| Latest independent review | Independent code-review agent, current session | Rejected: 403 response shape and ARM state did not distinguish ACA ingress denial from app-generated 403 |
| Narrow follow-up review | Independent code-review agent, current session | Passed the revised deny-evidence gate: calibrated ACA HTTP diagnostics, request correlation, no upstream attempt/app log, and block-on-ambiguity |
| Design amendments | [Design](design.md), [exit criteria](exit-criteria.md), [risk register](risk-register.md) | Locked-WORM records, fail-stop supervisor, signed absolute expiry, four ordered one-shot POSTs, dedicated internal ACA environment/VNet, and calibrated ACA diagnostic evidence are design targets only; all controls remain unimplemented and unverified |
| Azure Blob immutability research | [Immutable storage overview](https://learn.microsoft.com/azure/storage/blobs/immutable-storage-overview) | Microsoft Learn states locked time-based policies prevent modification/deletion during retention; actual account/container policy and effective identity permissions remain unverified |
| Candidate architecture | [Design](design.md) | Independent gateway, durable one-use authorization, private app route, no gateway ARM rights; design target only |
| Current shared ACA environment | [Table rollout evidence](../table-production-autoscaling/evidence.md) | Same-environment bypass not tested. Current shared app is not approved as watchdog target; the design now requires a dedicated internal ACA environment/VNet and a new G1 packet/budget |
| Watchdog implementation/deployment | None | This watchdog design work changed no source, infrastructure, Azure resources, ingress, or provider traffic |
| Independent full review | Separate review session | Rejected with seven Majors: fresh four-case scope, router retries/failover, runner control-plane bypass, delayed renewal, expiry/dispatch race, post-restart DENY proof, and residual shared-environment fallback |
| First full re-review | Same independent review session | The seven earlier findings were addressed as design requirements; one Major remained: fresh financial/process state immediately before each dispatch |
| Final design re-review | [Independent review](design-review.md) | Approved design only; all eight Majors addressed as requirements, no new Critical/Major findings. Network isolation, sole writer, operator separation, clocks, WORM, attempt limits and DENY diagnostics remain unverified; the review itself did not authorize implementation or execution |
| Operator stage approval | User message | User approved all stages, including implementation, Azure validation, and execution. This is stage-level approval; no exact infrastructure or paid-execution packet was presented or approved |
| Documentation verification | Local plan files | Twelve relative links resolved; plan-file trailing-whitespace/final-newline checks and `git diff --check` passed. This amendment changes documentation only; runtime, Docker, and Azure validation were not run for it |
