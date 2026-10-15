# Independent release-packet review

Verdict: **Approved for the nine bounded isolated staging cases**. Production promotion and production cases remain conditional on the handoff and staging gates below. October 13, 2026. This reviewer authored neither implementation nor release packet and made no implementation changes or paid calls.

## Exact reviewed scope

- `release-packet.json`, image build ca3, Linux/amd64 digest `sha256:a91fc53fac19212103ada1f304b492b6f6c9be355a766f87351859a68e290aec`.
- `acceptance-manifest.json`, canonical manifest SHA-256 `423915f04e4810fb9b68ccce6af68bf7350aabffe12953d4c6d46e0e53b4ff69`.
- Changed `policy_projection` in `scripts/quality/opencode_five_validation.py`, its call sites and runner tests; prior plan and implementation reviews and public evidence.

Direct local verification confirmed the manifest exactly equals the runner-generated fixed eighteen-case manifest; image/policy/request/manifest bindings match the public release packet. Nine staging and nine production cases preserve all five exact physical models, provider wires, prices, request/token/time limits and Sonnet nonstream-only scope. OpenCode 0.10 USD staging and 9.90 USD production seeds are disjoint under the approved 10 USD allocation, with 0.05 USD/5% reserve. No automatic transfer of unused staging credit is included.

The changed projection excludes only inherited account initial estimates; it retains their cycle/reserve/account membership and preserves the fixed OpenCode initial seed. Independent synthetic mutation checks confirmed inherited initial-seed changes leave the fingerprint unchanged while OpenCode initial-seed changes alter it. The runner suite was independently re-executed: **12 passed**. Prior Major fixes remain intact.

## Findings

No unresolved Critical or Major findings in the reviewed packet/projection scope.

**Suggestion — persist projection boundary regression**

- **File/Module:** `tests/unit/test_opencode_five_validation.py` / `policy_projection`.
- **The Issue:** The new selective seed-exclusion behavior is not yet a dedicated persisted regression test.
- **Why Static Analysis Missed It:** Static tools cannot identify which account fields intentionally remain part of the immutable approval boundary.
- **Impact:** A future refactor could accidentally exclude OpenCode seeds or include changing inherited seeds.
- **Recommended Fix:** Preserve the two mutation checks described above as a unit test when next changing the runner. Current behavior was directly verified during this review; this suggestion does not block staging.
- **Disposition:** Deferred to coordinator; current independent checks supply immediate evidence.

## Remaining gates and scope limits

The coordinator reports ca3 build/pull and zero-inference isolated Docker readiness succeeded. This reviewer verified the public digest binding but did not independently inspect registry/build records, private config packets or the running container. The public staging full-config hash is an attestation of a private exact configuration; it cannot be independently recomputed from this public packet. The executor must match the exact private full-stage configuration to that hash and confirm its reviewed Google low-thinking/pricing values before dispatch. The admin policy projection alone does not expose every native profile value or prove a running image digest.

Any failed/ambiguous stage slot must halt without replay or substitution. Complete all nine staging cases and stop the isolated staging writer before promotion. Production requires proven effective ingress denial/no bypass, successful read-only localhost exec, unchanged memory process identity, final drained all-account snapshot while readable, then all old writers stopped. Before promotion bind that final snapshot, exact all-account seeds, pinned secret payload/full-config hash, image digest and the unchanged manifest hash in an immutable handoff artifact and cross-check actual deployment inputs. No stale memory seed restoration is permitted. Production remains memory-backed, one worker and max one replica; original ingress restrictions are restored only after acceptance.

Public evidence still contains earlier in-progress build/re-review language; coordinator should append final ca3 and corrected verification outcomes so chronology cannot be mistaken for current status. Sonar script remains absent, not passed. Live model compatibility, production handoff and production acceptance are not established by this review. Material changes to image, model requests, pricing, credit allocation or handoff invalidate approval for the changed scope.
