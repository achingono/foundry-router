# OpenRouter production roster amendment (draft — pending independent review)

Date: 2026-10-12. Status: **Proposed; no code or configuration changed.**
Extends the Zen-first production scope with five paid OpenRouter pools,
non-streaming only. The streaming exclusion, paid-only rule, and per-case
staging validation gates are unchanged. No live dispatches authorized.

## Roster (verified against `GET /api/v1/models` 2026-10-12)

| Pool | Deployment | In / Out per 1M | Basis |
|---|---|---|---|
| `gpt-6-luna-or` | `openai/gpt-6-luna` | $0.10 / $0.50 | 6.2T weekly OR volume; efficient GPT frontier |
| `claude-haiku-5.5-or` | `anthropic/claude-haiku-5.5` | $0.10 / $0.50 | Fastest measured (240 tok/s); 1.09T new-week volume |
| `deepseek-v4.1-flash-or` | `deepseek/deepseek-v4.1-flash` | $0.15 / $0.60 | #1 OR volume (25.6T); value consensus |
| `mimo-v2.6-flash-or` | `xiaomi/mimo-v2.6-flash` | $0.14 / $0.28 | Cheapest above quality floor; Pro sibling leads open weights |
| `muse-spark-1.3-contributor-or` | `meta/muse-spark-1.3-contributor` | $0.10 / $0.20 | 1.43T volume; Meta-ecosystem open model |

Flagships (`claude-sonnet-5.5`, `claude-opus-5.5`, `gpt-6-astra`) and all
`:free` variants are explicitly out: wallet fit and rate-limit/availability
terms respectively. See roster rationale in session record 2026-10-12.

## Configuration contract

- One backend per deployment (existing per-deployment rule); all five share
  the `or-shared` credit group — no new money pools, no reserve-map change.
- `models_json` gains the five pools (single-backend weight 1.0);
  `pricing_json` uses the catalog-verified list prices above, re-verified day-of.
- Streaming stays excluded for OpenRouter (mocked-only per prior decision);
  pools serve `responses` non-streaming via the Chat-translation dialect.
- Effective ~$0.0004–$0.0009 per 2k-in/1k-out request; ~5,000+ requests of
  runway on the confirmed $4.83 balance before top-up (plus 5.5% fee).

## Acceptance

- Independent review of this amendment before implementation.
- Staging validation of the five pools under a new reviewed run identity
  (existing passes stay closed); production seeds cover all retained groups
  on the memory restart per the reserve amendment.
