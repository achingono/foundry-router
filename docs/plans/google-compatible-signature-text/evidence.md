# Signature text Evidence

Safe project3diagnosis: google object contains thought_signature string, small lengthclass;
unknown counts0. No signature bytes retained.

## Local implementation, 2026-10-08

Google request-local context now permits the exact bounded signature wrapper only for
stateless text. Generic normalization hooks preserve strict behavior for other providers.
Nonstreaming messages and fragmented SSE deltas retain text, usage and terminal events;
unknown state, malformed wrappers and ineligible requests remain rejected.

The fixed eight-case acceptance runner shares the historical ledger and stage lock, with
an immutable baseline, project-specific durable failure stops and strict validation of
persisted success and failure envelopes before display or resume. No live calls yet.

- Focused adapter/runner/diagnostic verification: 62 passed; immutable characterization
  fixtures also passed unchanged.
- Full suite: 1,829 passed, 3 skipped, 18 deselected; coverage 89.72%.
- Ruff lint/format and strict mypy: passed, 69 source files checked.
- Docker build passed; network-disabled Python 3.12.15 app import and signed-text
  translation smoke passed. Initial smoke used the image's Uvicorn entrypoint incorrectly;
  rerun with the Python entrypoint passed.
- Contextual independent implementation review cleared the adapter and runner after
  correcting validation of persisted failed results. No Critical/Major findings remain.
- SonarQube script is absent. Production configuration remains memory/one.
