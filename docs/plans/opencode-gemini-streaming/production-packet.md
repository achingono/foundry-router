# Subset production packet (pre-promotion)

Status: **Final, pending independent production-packet review before promotion**. Hashes and non-secret scalars only.

## Release

- Image: ca7 `sha256:b4b84283527eb19f86b19d53458621a0da9d653b64b36d74841efe580b423bbc` (verified live in ACR; staging passed 5/5 on this digest).
- Mode: additive. All 8 existing pools, 14 backends, aliases, weights, client/admin keys retained. Three pools added (Flash/Argon streaming-enabled, Sonnet nonstream-only). Memory state, one worker, max one replica retained.

## New vault secrets (all Gala Baking CO)

- `production-subset-backends-20261014` ver `fde757e38a2643b2954c334d04466068`
- `production-subset-models-20261014` ver `9addc590eaa04b39a024a33036b944f5`
- `production-subset-pricing-20261014` ver `82f51a94aa21454aa42ec5e06df04e3f`
- `production-subset-start-20261014` ver `cf2f70c7280044b29af798abd569773c`
- `production-subset-allowance-20261014` ver `7e12c7f81abb4f43b0c0083df639726f`
- `production-subset-initial-20261014` ver `f4031377a69d452d8216f5153985f60f`

Client/admin key secrets untouched (no rotation).

## Seeds and reserves

- Existing groups reconciled from the drained live snapshot (zero reservations): fs-openclaw 0.0, fs-swarm 83.621184, or-shared 4.81; allowances and cycle days unchanged.
- opencode-account: allowance 9.90, initial 9.90, cycle day 14, reserve override 0.05/5% (mirrors or-shared; global remains 10.0/5.0).
- Projected production fingerprint: `c12d9288d1611997ae7193325721775437d7aa2d92ed1cc1809f5ae4d53c9c29` (measured from a mirror running these exact docs on ca7; subset manifest `148ae26b…` binds it).

## Promotion sequence

1. Confirm old writer still the only revision and still drained (zero reservations) via replica exec.
2. Deactivate `foundry-router-production--or-two-20261012`; verify zero active revisions/replicas.
3. Repoint the six config secret refs to the versions above, set reserves env (or-shared + opencode overrides), update image to ca7 (single revision update; barrier Deny stays throughout).
4. Verify new revision healthy with expected image; read admin via replica exec and confirm live fingerprint equals the projected one plus zero reservations.
5. Add a single temporary executor-IP Allow rule; execute the five production slots; remove the Allow rule.
6. Verify production acceptance, then remove the drain Deny rule to restore original open ingress; final readback (pools/backends/flags/seeds/reservations).

No step replays consumed slots; any failure halts for a reviewed amendment.

## Slot enumeration and exclusion

Production dispatches exactly five slots, in order: `production-0-nonstream` (Flash), `production-0-stream` (Flash), `production-1-nonstream` (Argon), `production-1-stream` (Argon), `production-2-nonstream` (Sonnet, nonstream-only; `stream:true` rejected pre-egress). Grok (`grok-4.7-zen`) and Muse (`muse-spark-1.3-zen`) pools are excluded from this deployment on the recorded Grok over-bound failure and unconsumed Muse slots; no Grok/Muse backend is created, no alias remaps to them, and no model substitution is permitted. Staging passed the mirror five slots under the same identity.
