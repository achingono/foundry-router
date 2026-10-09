# Quota activities

1. Obtain independent session review of the concrete storage/lifecycle contract.
2. Add opt-in configuration and a shared effective-limit helper used consistently.
3. Implement bounded atomic per-group quota state and typed fail-closed errors.
4. Add lifecycle persistence/discovery, conservative expiry, clock and fingerprint checks.
5. Wire store construction, identity client lifecycle/readiness and routing admission safety.
6. Verify atomic fake-client, API, real local Azurite concurrency/restart and old memory tests.
7. Update canonical configuration/operations/traceability and review final implementation.
8. Run full quality gates, document exact evidence and commit the phase transition.
