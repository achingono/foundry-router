# Phase 07 Outputs

## Deliverables

| Output | Destination | Description |
|---|---|---|
| Configuration Settings (Phase 07) | `src/foundry_router/config/__init__.py` | 5 new environment-configurable fields: http_max_connections, http_max_keepalive_connections, http_keepalive_expiry_seconds, http2_enabled, graceful_shutdown_timeout_seconds (**Implemented**) |
| HTTP Client Connection Pool | `src/foundry_router/backends/__init__.py` | AllowedBackendClient uses httpx.Limits with configurable pool parameters; HTTP/2 multiplexing optional (**Implemented**) |
| Graceful Shutdown with Draining | `src/foundry_router/main.py` | Request tracking counter, track_active_requests middleware, _drain_active_requests() waits up to timeout for in-flight requests to complete (**Implemented**) |
| Bicep IaC Templates | `infra/main.bicep`, `infra/parameters.*.json` | Modular Bicep: Container Apps environment, Log Analytics workspace, Key Vault, container app with health checks and environment configuration (**Implemented**) |
| Deployment Documentation | `infra/README.md` | Comprehensive guide: prerequisites, deployment steps, resource overview, configuration reference, monitoring/diagnostics, security considerations, cleanup (**Implemented**) |
| CI/CD Deployment Pipeline | `.github/workflows/deploy.yml` | GitHub Actions workflow: build/push container image, validate Bicep, deploy staging on main push, manual production deployment, smoke tests (**Implemented**) |
| Operational Smoke Tests | `scripts/operations/smoke-test.sh` | Bash script: health checks (/live, /ready), admin diagnostics, model listing, observability validation, retry logic with configurable timeout (**Implemented**) |
