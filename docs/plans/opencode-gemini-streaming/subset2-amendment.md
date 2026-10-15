# Corrective amendment: live-measured production fingerprint + fresh staging

Status: **Planned** pending independent review. The subset manifest's doc/mirror-derived production fingerprint (`c12d9288…`) does not match live production (`4dd3f58f…`); production cases fail closed. No inference served; barrier holds.

## Cause

Two server resolutions are invisible in config docs: live production retains the codex aliases (`codex-auto-review`/`codex-auto-approve` → `gpt-6.1-sol`; the scratch mirror env had none) and normalizes the vault's int allowance `210` to float `210.0`. Recomputing the projection from live reads with both resolutions yields exactly the live value, so the live config is correct — the packet, not production, was wrong. Standing rule from this amendment: production fingerprints must be measured from a live admin readback (replica exec), never derived from docs or alias-less mirrors.

## Scope

New identity `opencode-zen-five-subset2-20261014`: same ten slots (five staging, five production; Flash/Argon both modes at 512, Sonnet nonstream-only at 128; Grok/Muse excluded on the recorded failure). Staging fingerprint from a fresh writer; production fingerprint pinned to the live-measured `4dd3f58f…`. No replay of consumed slots; no code changes; image stays ca7.

## Funding

Subset staging spent 0.001747 of the authorized 0.09, leaving a ledger-proven true remainder of 0.088253 (the retired writer's post-restart 0.09 display is a memory reset, not funds). Authorize carry-forward **R2 = 0.088253** as fresh staging funds for this identity (prior remainder explicitly re-authorized, not silently reused): staging seed **S2 = 0.085**, discarding 0.003253. Required worst-case 0.029837 + 0.05 reserve = 0.079837 ≤ 0.085, margin 0.005163. Production seed unchanged at 9.90. Any shortfall halts; no production borrowing.

## Gates

Independent review of this amendment and the new identity, offline harness tests, staging packet review binding ca7 + the live-measured production fingerprint, then live staging (five slots) and the five production slots under the existing barrier/handoff procedure. The current production revision stays live-but-denied throughout; no rollback to stale writers under any circumstance.
