# Independent plan review

Verdict: **Changes required**. Fresh independent session `ses_ec7d898bcffet4OSnfH93C69ku` reviewed the current plan without authoring it. No Critical findings; three Major findings. Approval for the complete implementation plan and for paid diagnostic, staging or production execution is withheld pending these corrections and concrete execution bindings.

## Major 1 — Flash-only acceptance cannot clear the Gemini production gate

References: `index.md:22-26`, `exit-criteria.md:9-10`, `risk-register.md:15`; the preceding five-model plan's `nonstream-deployment-amendment.md:7-11`.

The eight-case gate adds only Flash streaming. Argon streaming remains an open decision, while the inherited production policy disables both Gemini streams and tests their rejection. Completing this gate therefore does not establish the requested Gemini streaming production outcome.

Required correction: describe Flash investigation as an intermediate milestone. Require exact-model streaming acceptance for both Flash and Argon, plus reviewed production streaming policies and acceptance cases, before clearing the overall production gate. A separate Argon diagnostic need not be automatic.

## Major 2 — Required acceptance-harness and configuration changes are excluded

References: `activities.md:8-11`, `outputs.md:10`; `scripts/quality/opencode_five_validation.py:26-32,76-90,299-308`; the preceding plan's `acceptance-manifest.anthropic-nullable.json:10-24`.

The current runner recognizes historical seven- or nine-case-per-environment identities, not the proposed eight-case identity. The ca6 policy disables Flash streaming. Prohibiting configuration changes while requiring a successful Flash stream makes the planned acceptance run infeasible.

Required correction: authorize narrowly scoped harness and staging-policy changes. Specify a recognized immutable identity, canonical case ordering, consistent Flash streaming policy, image/request/policy/full-configuration bindings, historical ca6 ledger/snapshot bindings and a new staging seed derived after the irrevocable diagnostic debit. Retain consume-before-egress, halt-on-failure and replay-refusal rules with regression coverage.

## Major 3 — New SSE diagnostic needs its own pre-dispatch approval gate

References: `activities.md:5-11`, `outputs.md:7`, `risk-register.md:14`; `scripts/quality/opencode_five_diagnostic.py:116-123,218-242,251-299`.

The activities dispatch the diagnostic before the listed testing and independent-review steps. The referenced executor is a previously consumed nonstream diagnostic with obsolete snapshot, balance and manifest bindings. Its earlier approval does not authorize a new SSE executor. A consumed identity and fsynced result alone do not specify durable consumption before egress.

Required correction: implement, test and independently review the concrete diagnostic before dispatch. Bind the fixed identity/path, code/native-body/profile/pricing and ca6 source-artifact hashes. Require exclusive consumption and file/directory fsync before egress; actual remaining estimate, justified conservative debit and reserve check; permanent debit on every outcome; one request with no retries or redirects; total 120-second deadline, identity encoding and aggregate raw-byte bound. Test framing, timeout, crash/replay and redaction offline. Export only fixed allowlisted keys/reason enums, count unknown keys and suppress arbitrary strings and translated SSE output. Preserve production's fixed 9.90 USD seed without transfer or replenishment.

## Earlier corrections and operational scope

The current text includes both earlier requested textual corrections: bounded shared-validator changes with nonstream regression protection (`activities.md:8`) and seven cases plus explicit Flash streaming (`activities.md:11`). The new findings concern remaining execution feasibility and complete production qualification.

Operator-owned drain separation is appropriate. Later use of its snapshot still requires the inherited barrier/process-continuity, readable drained snapshot, explicit empty-replica and fresh-handoff evidence.

## Review evidence

The reviewer inspected all seven plan documents, repository instructions and contextual-review prompt, relevant preceding rollout/amendments/reviews/manifests, diagnostic/validation scripts and tests, and the native decoder. Public manifest/request hashes were checked locally. The Sonar script is absent; no successful scan is claimed. The reviewer made no edits and dispatched no inference or Azure mutations. This report records that independent review; the plan has not been amended in response to these findings.
