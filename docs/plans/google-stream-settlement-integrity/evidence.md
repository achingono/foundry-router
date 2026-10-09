# Stream settlement Evidence

Plan prepared from one failed live cancellation debit and code inspection.
Forwarding currently uses available numeric counts before terminal completion in both
GoogleAttemptSettlement and stream-finally settlement. No correction implemented yet.
All five projects have consumed twenty retained requests; no live replay is planned.

Independent reviewer cleared the completion/fallback contract with no Critical or Major
plan findings. Explicit signed complete-prefetch exception preserves existing full-body
semantics. No runtime changes or new provider calls at plan review.

Implemented locally: ordinary stream attempt ownership retains the original cost estimate
while keeping valid observed input quota. Actual stream finalization permits precise cost
only after clean EOF and successful decoder finish. Fully validated signed prefetch retains
complete-body usage. Azure pass-through and nonstreaming accounting are unchanged.

Ten new boundary tests pass for actual decoder cancellation/transport/protocol failure,
successful completion/zero price, routing unstarted/started cleanup, signed complete-prefetch
and usage-only prefetch. Existing prehandoff cancellation, malformed first tool frame and
four blocked native media tests now require original estimates while retaining input quota.
Combined focused regression: 115 passed. Full verification: 2,046 passed, 3 skipped, 18 Docker/Azurite cases deselected, 89.76% coverage.
Ruff lint/format and mypy (70 source files) pass. Linux amd64 Docker build and network-disabled
forwarding import/Toronto timezone smoke pass. Updated relative links and diff whitespace pass.
Sonar scanner script is absent. Independent contextual review cleared the forwarding boundary
with no Critical or Major findings; reviewer independently ran all ten new tests.

No new live requests, production/deployment/billing change or rewritten historical result.
The final live cancellation failure remains acceptance evidence; this local correction does
not establish a new provider pass. All five cumulative Google request budgets remain exhausted.
