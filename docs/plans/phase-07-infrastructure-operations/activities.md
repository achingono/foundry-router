# Phase 07 Activities

## Step-By-Step Activities

1. **Infrastructure as Code Definitions**:
   - Author modular Bicep templates (`infra/main.bicep`, `infra/modules/container-app.bicep`, `infra/modules/key-vault.bicep`).
   - Configure ACA environment, Log Analytics workspace, Key Vault secrets, and container app configuration.

2. **HTTP Connection Pool & Keep-Alive Tuning**:
   - Add configurable pool limits (`max_connections`, `max_keepalive_connections`, `keepalive_expiry`) to `Settings`.
   - Enable HTTP/2 multiplexing on outbound backend clients.

3. **Graceful Lifespan Reservation Draining**:
   - Implement active request tracker in application lifespan context.
   - On shutdown, wait up to `GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS` for in-flight requests and streams to finalize credit reservations before closing backend HTTP clients.

4. **CI/CD Pipeline & Operational Smoke Tests**:
   - Build GitHub Actions workflow for staging/production deployment with preview environments.
   - Implement automated smoke test script `scripts/operations/smoke-test.sh` validating `/health/live`, `/health/ready`, model listing, and Responses forwarding.

## Review Focus
- Zero plaintext secrets in IaC parameters and logs.
- Clean connection pool reuse and socket exhaustion prevention.
- Graceful drain execution without dropped reservations on container redeployment.
