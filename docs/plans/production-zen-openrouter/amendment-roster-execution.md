# Roster staging execution amendment (draft — pending independent review)

Date: 2026-10-12. Status: **Proposed; no code, configuration, or live changes.**
Validates the five roster pools plus the reserves build on staging under new
immutable identities. Prior passes stay closed. No live dispatches authorized
by this draft.

## New run identity

- Run ID: `staging-or-roster-2026-10-12`, environment `staging`, prompt
  `Reply with the word ready.`, `max_output_tokens` 128, allowance USD 0.01.
- Five non-streaming `responses` cases (pool / deployment / in-out per 1M):
  - `roster-luna-nonstream`: `gpt-6-luna-or` / `openai/gpt-6-luna` / 0.10-0.50
  - `roster-haiku-nonstream`: `claude-haiku-5.5-or` / `anthropic/claude-haiku-5.5` / 0.10-0.50
  - `roster-deepseek-nonstream`: `deepseek-v4.1-flash-or` / `deepseek/deepseek-v4.1-flash` / 0.15-0.60
  - `roster-mimo-nonstream`: `mimo-v2.6-flash-or` / `xiaomi/mimo-v2.6-flash` / 0.14-0.28
  - `roster-spark-nonstream`: `muse-spark-1.3-contributor-or` / `meta/muse-spark-1.3-contributor` / 0.10-0.20
- Harness additions (reviewed code change required): `RUN_SPECS`/`RUN_CASES`/
  `RUN_FILES` entries for the new ID with `ledger-roster.json`/
  `results-roster.json`; `manifest.roster.json` pinned by a committed-manifest
  test like the existing two. No streaming cases (OpenRouter exclusion stands).

## Staging configuration and image

- Image: rebuild from the reserves-gated HEAD and promote by digest; the
  `4224eaa` staging image predates group reserves and cannot admit the
  `or-shared` balance under app-wide reserves.
- Vault updates (drained restart, temp grant removed after, all groups reseeded
  from live balances): five backends sharing `or-shared`, five pools, five
  catalog prices; `credit_group_reserves_json` gains the `or-shared` override
  (e.g. 0.05/5.0); Zen entries retained unchanged for the mixed-policy read.
- Live gates: operator quiescence, named approver, $0.01 combined allowance,
  halt-on-first-failure with no replay; results/ledger git-ignored as before.

## Acceptance

- Independent review of the harness diff and this amendment before any vault,
  deployment, or live change.
- 5/5 pass with coherent usage, matched settlement, cleared reservations, and
  mixed-policy admin evidence closes the reserves code-validity gap; OR-3 then
  needs only the production-execution amendment.
