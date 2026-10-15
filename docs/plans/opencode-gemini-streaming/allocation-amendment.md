# Allocation amendment: fresh bounded staging budget

Status: **Planned** pending independent review. October 14, 2026. Operator authorized "as much as is needed to cover the bounded staging budget."

## Provenance

- Fresh isolated staging funds only. No production borrowing, no transfer of unused staging, no reuse of prior discarded amounts.
- Production OpenCode seed remains fixed at **9.90 USD**. Production currently holds no OpenCode account group concurrently, so the fresh staging allocation does not duplicate live funds.
- Prior staging identities (0.10 through 0.088) and their spends/discards are sunk and superseded. The ca6 remaining after seven successful cases is discarded, not carried forward.

## Bounded arithmetic (measured via repo estimator)

Fixed synthetic input `Reply with the single word OK.` estimates to 10 input tokens. Worst-case per-case reservation is `(10 × input_price + max_output_tokens × output_price) / 1,000,000`:

| Case | Prices (in/out per M) | Max out | Worst reservation USD |
|---|---|---|---|
| Flash nonstream | 1.50 / 7.50 | 512 | 0.003855 |
| Flash stream | 1.50 / 7.50 | 512 | 0.003855 |
| Argon nonstream | 4.00 / 20.00 | 512 | 0.010280 |
| Argon stream | 4.00 / 20.00 | 512 | 0.010280 |
| Sonnet nonstream | 4.00 / 10.00 | 128 | 0.001320 |
| Grok nonstream | 4.00 / 12.00 | 512 | 0.006184 |
| Grok stream | 4.00 / 12.00 | 512 | 0.006184 |
| Muse nonstream | 1.25 / 4.25 | 512 | 0.0021885 |
| Muse stream | 1.25 / 4.25 | 512 | 0.0021885 |
| **Nine-case staging total** | | | **0.046335** |

Required reserve: 0.05 USD / 5%. Staging seed must satisfy `S >= 0.046335 + 0.05 = 0.096335` before input variance.

Diagnostic debit (Flash stream worst-case 0.003855, rounded conservatively): **D = 0.004 USD**, irrevocable on every consumed outcome including transport failure or crash.

## Authorized amounts

- Fresh total staging funds: **R = 0.104 USD**.
- Diagnostic debit: **D = 0.004 USD**.
- New eighteen-slot staging seed: **S = 0.10 USD** (`S = R - D`, no additional discard).
- Check: worst staging 0.046335 leaves 0.053665, preserving the 0.05 reserve with 0.003665 margin. No stage may start unless `R - D - S >= 0` and the live reserve gate holds.
- Production seed unchanged at 9.90 USD. Any shortfall halts for a further reviewed amendment; never borrow production funds automatically.

## Binding

- New recognized harness identity `opencode-zen-five-gemini-streaming-v1` binds `staging_allocation_usd: 0.10`, `production_seed_usd: 9.90`, full nine-per-environment cases with both Gemini pools streaming-enabled.
- Diagnostic packet binds R, D, code/body/profile/pricing hashes and ca6 source-artifact hashes before dispatch.
- Staging packet binds S, final image digest, exact requests, both policy fingerprints and complete historical chain (including diagnostic consumed/result artifacts).
- These are local cost estimates, not authoritative provider balances.

## Gates

Independent review of this amendment, then harness/test implementation with the fixed seed, then separate diagnostic/staging/production packet reviews before each live gate. Paid execution remains blocked until those reviews pass.
