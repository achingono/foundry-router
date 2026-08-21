# Architecture

## Objective

The target system is a small asynchronous HTTP proxy hosted on Azure Container Apps. It receives an OpenAI-compatible request, selects a configured backend, forwards the request without changing the logical model name, streams or returns the upstream response, and records health, quota, usage, and estimated cost state.

```text
Client -> OpenAI-compatible API -> Foundry Router -> configured Foundry backends
                                      |                 A / B / ...
                                      +-> cost reconciliation and telemetry
```

## Boundaries

- API adapter owns validation, authentication, protocol translation, and response pass-through.
- Backend client owns outbound HTTP, timeouts, streaming, and safe header handling.
- Routing owns candidate selection, scoring, weighted selection, state transitions, retry, and failover.
- Credit subsystem owns cycle calculations, pricing, reservations, estimates, and reconciliation.
- Telemetry owns structured logs, metrics, correlation IDs, and redaction.
- Infrastructure owns Azure resources, identity, secrets, RBAC, and deployment.

Keep these responsibilities separate. In particular, estimated local cost is not authoritative Azure cost, and model quota is not subscription credit.

## Deployment Shape

The initial target is Azure Container Apps Consumption with 0.25 vCPU, 0.5 GiB memory, zero minimum replicas, and at most two replicas. Scale-to-zero must remain possible. The design must tolerate more than one replica without corrupting reservations or credit accounting; shared authoritative state or an explicitly safe reconciliation strategy is required before scaling stateful routing beyond one process.

## Technology Direction

The preferred stack is Python 3.12+, FastAPI, asynchronous `httpx`, Pydantic settings, Docker, Azure Container Apps, one consistently chosen IaC technology, GitHub Actions, pytest, Ruff, and mypy or pyright where practical. These are design targets until implemented.
