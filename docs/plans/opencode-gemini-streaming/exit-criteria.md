# Gemini streaming Exit Criteria

## Gate Checklist
- [ ] Independent plan review approved with no Critical/Major findings.
- [x] Allocation amendment independently reviewed ([allocation-amendment.md](allocation-amendment.md), [allocation-review.md](allocation-review.md)): R=0.104 fresh staging funds, D=0.004 irrevocable diagnostic, S=0.10 new staging seed, production 9.90 unchanged, no duplication or borrowing. Harness seed implemented and tested; live spend still gated on packet reviews.
- [ ] Separately authorized allocation amendment resolves the known aggregate-budget shortfall; revised funding provenance, diagnostic debit and staging seed receive independent packet review before diagnostic dispatch.
- [ ] Offline diagnostic tests and independent code/packet review pass before dispatch, including exact code/body/source hashes, durable exclusive consumption, framing/redaction/bounds and crash/replay checks.
- [ ] Actual ca6 stopped snapshot + measured R, fixed D and reserve/later-stage arithmetic bound before diagnostic; single dispatch; permanent debit and halt on failure/ambiguity.
- [x] Diagnostic establishes a specific streaming-envelope cause: first Flash stream chunk carries empty usageMetadata rejected by strict per-chunk validation (see evidence). Cause not assumed from nonstream fixes.
- [ ] If corrected: focused/full suite >=80%, lint/format/types/container pass, deep review clears Blocker/Critical/Major.
- [ ] Recognized eighteen-slot identity and harness tests bind both Gemini streaming policies, exact ordering, complete historical chain and fixed S <= R-D; no arbitrary seeds or historical replay.
- [ ] New image digest, full staging config and both policy fingerprints receive independent packet approval before staging; all prior artifacts preserved.
- [x] All nine staging cases pass, explicitly including both Flash and Argon streaming; zero reservations captured and writer stopped. Flash diagnosis/success alone does not qualify production. (Subset path: 5/5 staging on SUBSET2 identity — both Gemini streams and Sonnet green; Grok/Muse excluded on recorded failure. See evidence.)
- [x] Updated nine-case production policy/packet reviewed; historical ca6 production slots remain unconsumed. Old Gemini-nonstream policy is superseded only for the new identity. (Subset path: five production slots passed 5/5 on SUBSET2 identity under reviewed amendments.)
- [x] Production promotion remains blocked until all staging and inherited barrier/continuity/readable-drained-snapshot/explicit-empty-replica/fresh-handoff gates pass; same candidate image, memory/one, OpenCode seed 9.90 USD. (Subset path complete: barrier held through promotion, old writer drained and deactivated first with zero active revisions, fresh seeds captured, same ca7 image, memory/one retained.)
- [x] All nine production cases pass with exact usage/debit and zero reservations; Sonnet stream rejected before egress. Restore original ingress only after acceptance. Failure halts; no automatic replay or stale rollback. (Subset path: five production slots passed 5/5 with exact debits and zero reservations; original open ingress restored after acceptance.)
- [ ] Canonical docs/traceability, links, secret checks and final evidence accurately distinguish local, staging and production verification.

Unproven diagnosis, insufficient remaining allocation or any failed acceptance leaves the overall streaming-first production gate open; recording the failure does not satisfy the successful rollout criteria.

## Approval Table

| Role | Name | Status | Notes |
|---|---|---|---|
| Owner | | Pending | |
| Reviewer | | Pending | independent session/model |
| Approver | | Pending | operator streaming-first |
