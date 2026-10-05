# Activities

1. Independently review before requests.
2. Retrieve production client/admin keys through captured token-authenticated vault reads. If current operator lacks data access, grant temporary Secrets User on the production vault and remove precisely that assignment afterward. Do not overwrite secrets or log values.
3. Snapshot canonical groups and model discovery. Sequentially send one nonstream and one streaming Responses request per six model pools, max_output_tokens128, storefalse, low reasoning effort where accepted, total deadline180s/read120s. Initial12 requests; investigate errors before retrying. Never retry after meaningful stream output.
4. Record HTTP/completion/usage/event types only, no prompt/output/auth/error-body logging. Check stream deltas, completed terminal usage and no partial frame. Compare sum of canonical group debits with input/output usage at each model's configured price; report estimates, not Azure bill amounts. Require zero inflight/reservations after settlement.
5. Record backend request-counter deltas where available to identify routing coverage. Do not claim both resources for every model if only one was selected. Production settings and balances are not reset for testing.
6. Remove temporary vault access in finally, verify readiness, and document success/failures and remaining Table/failure/cost gates. Evidence-only unless defect requires independently reviewed code correction. No commit/push after test without user request.
