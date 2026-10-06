# Actual process restart replay verification

**Planned**,2026-10-06. This closes the existing reviewed signed-continuation restart requirement;
no runtime or public contract changes are proposed. Existing tests recreate runtime objects but
share Python process state and therefore do not establish restart behavior.

Use two independent Python interpreters running a standalone synthetic harness with init-only
Settings, isolated FastAPI router/memory stores, real signed intake/adapter/backend boundary,
OpenAI2.8.1 client transport and fixed MockTransport provider. First process creates signed
output; parent retains that synthetic carrier in memory and feeds the replay body over stdin to
a second fresh process. Each process receives the same fixed synthetic caller/backend/model/
state-key/configuration identities; no real credentials, environment configuration or network.
No production main globals/lifespan. Both processes shut down owned SDK/provider clients.

First output includes a nonempty synthetic native thoughtSignature; the second provider must
receive the exact original native Part and signature association and no public state carrier.
Both processes independently admit/charge known usage once, zero credit/quota reservations
and released two signed work slots. A changed-key second process must reject422 before dispatch.
Use strict pinned SDK Response serialization; no stdout/logging of body/signature/output. The
harness may send bounded synthetic JSON through a private subprocess pipe solely to the parent
fixture; final retained evidence includes only status/dispatch counts/usage/cleanup/PID difference.
Parent checks no synthetic markers in captured logs/error/summary; timeouts terminate child and
report safely. subprocess cwd/read paths point at repository; no persisted state/key files.

Run focused tests, full coverage>=80%, Ruff/format/mypy, Docker image smoke and independent deep
review; report Python version and exact fresh-process scope. Linux/container process verification
can follow using the same network-disabled image. Startup remains gated: this is synthetic
process evidence, not provider/live/production compatibility. Submit this concrete verification
amendment for independent review before adding harness/tests.
