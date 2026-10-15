# Independent diagnostic packet review

Verdict: **Blocked — diagnostic packet not approved**. Independent session `ses_ec390cf08ffeHvmaA4MfC3MB3h` inspected the current executor, tests, plan and available private artifacts. Scope is the next Flash streaming diagnostic only, not staging or production. No provider inference or Azure mutation occurred.

## Major findings

1. **Missing concrete packet and executor inputs.** Executor references `ca6/` and `stream-funds-admin.json`, which are absent. Actual ca6 artifacts are `runner5/`, `staging5-final-admin.json`, `stage5-container-id.txt` and `staging5-stopped.json`; the stopped artifact does not have the executor's expected schema. Build a reviewed immutable packet referencing preserved actual artifacts; do not fabricate a runtime snapshot containing the new allocation. References: executor lines 161-163 and 328-336; activities diagnostic contract.
2. **Pinned independent approval is not enforced before egress.** The executor records current hashes but does not compare them with an independently approved packet. Its source hash excludes imported runtime dependencies. Require reviewed packet approval and exact executor/dependency/native-body/funding/history hash comparisons before consumption or dispatch. References: executor lines 398-426 and 482-484.
3. **Funding provenance, historical debit reconciliation and writer exclusion are not enforced.** A locally constructed JSON estimate can satisfy funding validation. Historical remainder is not reconciled against ca6 debits; self-consistent historical mutations and asserted stopped state are not compared against pinned independent evidence. Bind the fresh allocation separately from historical snapshots, reconcile debit history and establish fresh stopped-container/account-writer exclusion evidence. References: executor lines 329-374; allocation amendment provenance/binding sections.
4. **Framing repairs an unclean EOF.** Splitting an unterminated final frame and appending a blank-line delimiter makes the diagnostic accept a STOP event that the production decoder rejects. Feed original bytes without synthesizing delimiters, retain trailing incomplete data and add clean/unclean EOF regressions. References: executor lines 223-224, 239-241 and 247-307; native decoder lines 745-748. Reviewer reproduced the mismatch offline.
5. **Pre-existing result-only state permits dispatch.** An existing result without a consumed marker is rejected only after provider dispatch, at result write. Reject all pre-existing ambiguous identity state before egress under an exclusive claim; assert zero HTTP calls for this case. References: executor lines 396-425 and 482-485; diagnostic tests lines 323-328.

Line references describe the reviewed version and may shift during remediation. Reviewed executor SHA-256: `2e25e18d9f6070fa9116e1cd7ef8f8999ddebb370edb784e06df9aa3147e6bfb`.

## Actual historical evidence verified

- ca6 manifest SHA-256 matches its public pinned artifact: `7d30655fb285a9d14efe6eb54c41940c3229383100ddd05fd01488ec68bf94cb`.
- Identity/ledger bind that manifest; canonical cases match. Seven staging results pass the existing validator; seven production slots remain unconsumed.
- ca6 debit sum is 0.01787075 USD; 0.088 minus that sum is 0.07012925 USD, matching its final snapshot with zero reservations.
- Read-only Docker inspection confirms the recorded ca6 container is exited and uses the expected image. This alone does not prove absence of every remote/concurrent account writer.
- Original staging allocation reconciles: 0.02762425 spent + 0.00224650 previously discarded + 0.07012925 final remainder = 0.10 USD. The amendment discards the final remainder; fresh 0.104 USD is not ca6 runtime remaining credit. Production stays 9.90 USD.
- Fresh allocation arithmetic is sound as a local estimate: 0.104 minus 0.004 gives 0.10; the nine-case estimate leaves 0.053665 USD, above the flat reserve.

## Controls and disposition

Correct native route/body/profile, request bounds, no retries/redirects, identity encoding, create-only durable consumption, aggregate byte/event limits and fixed-key/reason redaction are present. These are code/design observations, not concrete execution approval. Preserve earlier reviews as historical; remediate all five Majors and obtain a fresh independent packet review before paid dispatch.
