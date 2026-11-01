# Watchdog Review Remediation Risks

- Financial fences and WORM attestation cannot substitute for separately reviewed real Azure retention, role or accounting evidence.
- Timeouts and cancellation may leave committed markers; never treat uncertain acknowledgement as permission or retry.
- App authentication must not expose credentials to logs, reprs, arbitrary destinations or unauthenticated callers.
- Review fixes are local primitives only; process wiring, privileged operator separation, runtime quiescence and Azure denial-log completeness remain separate gates.
- The pre-existing staged index is user work; never reset, unstage, or silently restage it.
