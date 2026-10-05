# Evidence

| Item | Reference | Notes |
|---|---|---|
| Implementation commits | b623c37, 7973756 | Shared-resource credit and production deployment committed separately |
| Plan review | Independent session | Approved 12 bounded sequential requests and routing-coverage caveats |
| Request settings | Production app | max_output_tokens128, storefalse, low reasoning effort; no prompts/outputs/credentials recorded |
| gpt-5.6-luna | Nonstream/stream | Both HTTP200/completed; input12/output11 each; estimated debit0.0000156 each; stream15 events |
| gpt-5.6-terra | Nonstream/stream | Both HTTP200/completed; input12/output6 each; debit0.00012 each; stream10 events |
| gpt-5.6-sol | Nonstream/stream | Both HTTP200/completed; input12/output6 each; debit0.000108 each; stream10 events |
| gpt-6-luna | Nonstream/stream | Both HTTP200/completed; input12/output8 then11; debit0.0000052/0.0000067; stream15 events |
| gpt-6-astra | Nonstream/stream | Both HTTP200/completed; input12/output7 each; debit0.00047 each; stream11 events |
| gpt-6.1-sol | Nonstream/stream | Both HTTP200/completed; input12/output6 then7; debit0.000084/0.000094; stream11 events |
| Streaming/settlement | All six streams | Text delta and response.completed; terminal usage; no partial trailing frames; no inflight/active reservations after each request |
| Canonical accounting | Two shared resource accounts | Total observed debit0.0016171 matched returned usage at operator prices; local estimate, not Azure billed cost |
| Routing coverage | Request counter deltas | One fs-swarm backend request per test; fs-openclaw inference not exercised, no both-resource claim |
| Cleanup/readiness | Final checks | Production readiness healthy; temporary vault Secrets User assignment removed in finally |
| Remaining gates | Operations | fs-openclaw inference, provider failure/admission traffic, Table production cut-over and authoritative cost reconciliation unverified |
| Price inputs (USD per million) | Operator configuration | gpt-5.6-luna0.2/1.2; terra4/12; sol4/10; gpt-6-luna0.1/0.5; astra10/50; gpt-6.1-sol2/10 (input/output); not independently verified Azure billing rates |
| Final review | Independent session | Evidence arithmetic/routing scope checked; stale current status statements reconciled; no secrets or Critical findings |
