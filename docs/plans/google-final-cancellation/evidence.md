# Final cancellation Evidence

Plan prepared from three public completed early-delivery results and strict verifier stop
qualification failures. Their raw stop shape is unknown; no further calls in this phase.
At preparation, one project2 requestslot remained; other projects were exhausted. The final
execution below consumed that slot. Historical failures remain unchanged.

Implemented locally: an optional existing-adapter mirror independently validates received
provider frames while numeric usage maxima are captured first. Mirror output is discarded;
cleanup clears state without synthesizing EOF. The single-case runner checks pinned SHA256
normal-route evidence and matching ledger debits under the shared stage lock before credentials
or dispatch, preserves the current budget baseline, and refuses consumed-case replay.
Cancellation success requires disconnect before DONE, mirror terminal and EOF, natural
provider/reservation cleanup and independently recomputed conservative USD settlement.

Local verification: 88 focused checks pass, including signature-bearing text on stop,
malformed state retaining numeric usage, natural loopback cancellation, prerequisite tampering,
fallback debit validation and consumed-case replay without credential acquisition. Full suite:
2,035 passed, 3 skipped, 18 Docker/Azurite cases deselected, 89.76% coverage; an additional
same-chunk DONE/cancellation race test passed separately after suite collection. Ruff lint/format and mypy
(70 source files) pass. No runtime source or infrastructure change; previous Docker evidence
remains scoped to its recorded runtime. Sonar scanner script is absent. Independent contextual
review cleared the verifier changes with no remaining Critical or Major findings; reviewer
socket rerun was interrupted, so local execution results are the verification evidence.
The single live invocation is now retained in results (local-only `results.json`) and durable
progress (local-only `progress.json`). Both provider/public HTTP 200; exactly one dispatch, first
provider chunk 0.706178 seconds and meaningful public text 0.711838 seconds. Disconnect
preceded DONE, mirror completion and EOF; natural provider/reservation cleanup passed.
Independently observed input13/output1/total14 were complete numeric fields but not verified
terminal usage. Actual synthetic debit was $0.014, while the cancellation verifier required
the conservative full request estimate; settlement_matches=false, overall status=failed.
These are synthetic local USD accounting values, not provider billing or Azure balances.
The failure leaves cancellation settlement acceptance open; early delivery/cleanup are scoped
observed facts. Raw frames are not retained, so do not infer whether a stop choice was present
or why runtime selected the observed debit. Investigate locally before changing accounting.

Project2 now has 20 consumed requests and 18,368 reserved tokens, matching all other projects.
All request budgets are exhausted; no retry, new normal case, reset or additional provider
traffic is authorized by unused token headroom. No overrun, deployment, balance application
or production change. Historical failed statuses remain unchanged.
