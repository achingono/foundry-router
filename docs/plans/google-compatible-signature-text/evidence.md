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
persisted success and failure envelopes before display or resume.

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

## Live acceptance, 2026-10-08

[Persisted results](results.json) contain eight passes: one nonstreaming/streaming pair
on each of projects 2–5, exact `gemini-3.5-flash-lite`, compatible surface, provider-default
thinking. Public and provider HTTP status were 200 throughout. Every result contains
completed public text, matching terminal usage and synthetic settlement, with zero remaining
reservations. Six cases used 7 input/2 completion tokens; two used 7 input/1 completion tokens.
Synthetic debits were $0.009/$0.008 respectively, explicitly unrelated to provider billing.
Thought metadata was absent, so nonzero thinking settlement remains unverified.

The first invocation used an incorrect vault reference and refused before dispatch. Read-only
metadata lookup resolved the supplied secret in the production vault; no secret values were
displayed. The subsequent invocation completed all eight cases without retry or overrun.

[Shared cumulative ledger](../google-ai-routing-order/ledger-native-text-2026-10-08.json)
retains all historical failures and diagnostics. Project 1 is unchanged at 20 requests/
18,368 reserved tokens; projects 2–3 now have 18/16,192 and projects 4–5 have 17/15,104.
The immutable baseline remains unchanged. No production configuration changed.

The guard buffers bounded upstream streams before router consumption; these results establish
public SSE translation and settlement, not first-token latency or live upstream cancellation.
Project 1 repaired compatibility, other models, embeddings, tools/signed continuation, quota
ceilings, provider admission, Table real inference and production rollout remain separately gated.
