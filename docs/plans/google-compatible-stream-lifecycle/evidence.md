# Stream lifecycle Evidence

Plan prepared from historical buffered compatible success scope and remaining cumulative
budget. No new Google provider calls or runtime edits in this phase yet. Production unchanged.

Current cumulative budget inspection confirms project 1 has zero remaining request slots;
projects 2/3 each two slots and 3,808 reserved tokens, projects 4/5 each three slots and
4,896 reserved tokens. Ten 1,088-token dispatches fit this unchanged allowance. Independent
plan review cleared natural cancellation, early delivery and durable progress invariants.
Implementation and live execution remain pending.

First implementation portion adds verifier-only incremental usage observation and locked
monotonic progress accounting restricted to new deterministic stage cases. Fragmented and
multiline frames, partial/malformed/nonmonotonic usage, bounded frames/bodies, dimension and
reasoning-only overruns, terminal/EOF conditions, nonrefundable debits and historical-prefix
protection pass 20 focused tests. Independent review fixed reasoning lower-bound accounting
and cleared this portion. No Google calls sent and no production/runtime behavior changed.
Remaining server/client, case evidence, durable runner and final execution gates are open.

Full suite after the reviewed usage fix: 1,966 passed, 3 skipped, 18 deselected,
89.74% coverage. Ruff lint/format and mypy (70 runtime source files) pass. Documentation
links/diff whitespace pass; Sonar scanner script absent. Verifier-only phase needs no new
Docker build. This verifies the current portion, not the remaining lifecycle stage.

Owned loopback server/client and durable stage runner now implemented. Actual localhost
Responses-route tests prove early public text and natural disconnect cleanup, synthetic
inclusive thought settlement, rejection/ownership failures and retained partial overruns.
51 focused tests pass. Final full suite: 1,997 passed, 3 skipped, 18 deselected; coverage
89.74%. Ruff lint/format and mypy (70 runtime files), relative links and diff whitespace
pass. Contextual review cleared all Critical/Major findings; see
[review](implementation-review.md). Verifier-only work needs no Docker rebuild; Sonar
scanner script absent. [Immutable baseline](ledger-baseline.json) copies the existing full
cumulative ledger with no budget reset. No live requests sent in implementation.

## Single bounded live stage

[Results](results.json) retain six dispatches: project 2/3 ordinary streams, project 4/5
reasoning nonstream/stream pairs. Both nonstream cases passed (18 input +67 output=85 tokens
and .085 synthetic USD debit each). Four streams returned provider/public HTTP 200,
public completed events and matching input/output usage; local debits were .009, .009,
.080 and .086 USD. Natural upstream close and zero reservations passed all six cases.
No overrun occurred. Provider reasoning metadata was absent; nonzero thought settlement
remains unknown. Total observed usage 354 tokens; all six 1,088-token reservations remain
nonrefundable in the cumulative ledger.

All four streams remain failed under this verifier's terminal-usage acceptance: their
`terminal_usage` flags are false and the resulting conservative-fallback settlement check
is false despite retained actual numeric debits. Early public text before observed upstream
EOF passed projects 3/4/5 and failed project 2. The saved evidence cannot distinguish
missing final usage shape, early route closure or missing protocol termination; do not
infer a provider billing failure from these flags. A separate reviewed observer/acceptance
amendment is needed before further calls. Historical results remain immutable.

Every cancellation case was withheld after its preceding stream failed. No cancellation
live gate is cleared. Each project 2–5 now has one remaining cumulative request slot;
project 1 has none. Do not reset allowance or rerun consumed IDs. The stage's project failure
halts remain effective on replay. [Progress](progress.json) preserves numeric observations
before later awaits. Production remains memory/one and deployment approval remains pending.
