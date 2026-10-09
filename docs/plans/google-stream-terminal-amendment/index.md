# Compatible stream terminal usage amendment

**Planned**, 2026-10-09 UTC. The incremental stage retained four public-completed streams
with matching usage/debits but false verifier terminal flags. Cancellation was withheld.
No raw frames were retained, so their exact failure cause is unknown. A local synthetic
reproduction proves the verifier currently fails complete usage attached to a stop choice,
even with valid stop, [DONE] and EOF; runtime adapter accepts usage in that shape.

After independent plan review, adjust verifier-only IncrementalUsage to accept a complete
consistent usage object attached either to choices=[] or to one exact final stop choice:
exactly one index-zero choice, finish_reason=stop, delta object with only inert/empty
permitted fields and no meaningful content/tools/refusal/state. Reject later meaningful
output after that stop. The actual adapter continues owning full provider field validation.
Require complete integer input/output/total, inclusive reasoning subset, equal maxima,
no invalid/overrun flags and protocol stop+[DONE]+EOF. A nonterminal content/partial frame
never establishes final usage. Record fixed safe terminal facts (stop_seen, done_seen,
upstream_eof, final_usage_shape absent/usage_only/stop_choice) in NEW result/progress schema;
no frames, choices/content/signatures, headers or arbitrary strings enter evidence.

Keep the consumed six-case stage results and its baseline/progress immutable. The same
fixed-schema old reader must continue reading them; use a new reviewed stage/runner path
rather than rewriting old evidence or relaxing historical failures. Add at most three new normal
reasoning stream cases on projects 3–5 and one conditional cancellation stream on project2,
one remaining cumulative request slot per project, each1,088
reserved tokens /64input/1,024output/zero paid spend under existing user authorization.
Project1 stays excluded. Use the reasoning prompt already frozen for projects3–5. Project2
cancellation uses the frozen list prompt and is allowed only AFTER at least one new normal
reasoning stream passes all amended early-delivery/terminal/cleanup checks; it relies also
on project2 historical public completion/settlement evidence. If no normal stream passes,
withhold cancellation and retain that last slot. Do not reinterpret failed historical
terminal flags as passing; conditional cross-project prerequisite is explicit in this plan. Capture the current
ledger as a NEW immutable baseline, preserve every historical case/debit and all failed
lifecycle outcomes. No retries/reset, no cancellation call without a separately scoped
successful preceding proof and finite remaining allowance. Cancellation clears only project2/exactmodel/localroute if natural early disconnect and
conservative debit/zeroreservations pass; failure or withholding keeps the explicit gate
open. Do not reuse a prior failed outcome as approval.

Reuse owned real loopback client/server, immediate-forwarding usage observer, bounded
25srequest/<30stotal, natural close/zeroreservation checks and numeric persistence. Persist
safe terminal facts before later awaits; overrun globalhalts from authoritative ledger.
New stage's required normal success includes publictext-beforeupstreamEOF, completed/text,
complete matching inclusive usage/debit and natural cleanup. A fast provider that completes
before public text remains unverified for early delivery; do not artificially delay EOF.

Test attached-stop usage, usage-only usage, complete nonterminalusage rejection, partial/
malformed/multichoice/nonstop, duplicate/mismatched/nonmonotonic usage, bad thoughts and
protocol-truncated finalframes. Keep old saved results unchanged and readable; test new
safe terminal metadata schema and inherited budget/crash/replay gates. Full quality,
>=80%coverage and contextual review before execution. Verifier-only no new Docker build.
Commit plan, implementation and new bounded outcomes separately. Record proven terminal
shape or unknown precisely. No production/infra changes or provider quota probes.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
