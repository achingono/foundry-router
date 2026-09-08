# Phase 07 Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Plan review | `docs/plans/phase-07-infrastructure-operations/index.md` | Infrastructure & operations design |
| Configuration Settings | `src/foundry_router/config/__init__.py` | Added 4 new settings: http_max_connections, http_max_keepalive_connections, http_keepalive_expiry_seconds, http2_enabled, graceful_shutdown_timeout_seconds |
| HTTP Connection Pool | `src/foundry_router/backends/__init__.py` | AllowedBackendClient uses httpx.Limits configured from Settings; HTTP/2 multiplexing optional (default disabled) |
| Graceful Shutdown | `src/foundry_router/main.py` | Request tracking with _active_requests counter, track_active_requests middleware, _drain_active_requests() with timeout, integrated into lifespan |
| Bicep IaC Templates | `infra/main.bicep` | Azure Container Apps (0.25 vCPU, 0.5 GiB), Log Analytics workspace, Key Vault, configurable min/max replicas, environment-specific vars |
| Parameter Files | `infra/parameters.staging.json`, `infra/parameters.prod.json` | Staging: 0-1 replicas; Production: 1-2 replicas |
| Infrastructure Docs | `infra/README.md` | Deployment guide, security considerations, validation steps, cleanup procedures |
| CI/CD Pipeline | `.github/workflows/deploy.yml` | Multi-stage workflow: build image, validate Bicep, deploy staging with smoke tests, manual production deployment |
| Smoke Tests | `scripts/operations/smoke-test.sh` | Bash script with retry logic: checks /health/live, /health/ready, /admin/status, /metrics, /openai/v1/models |
| Test Results | All 227 tests passing | No breaking changes; all existing tests pass with new settings/middleware |
| Integration | Phase 06 output | Uses same Settings instance, integrates with existing health/credit/metrics stores |
