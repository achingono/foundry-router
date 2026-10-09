# Cost reconciliation risks

| Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- |
| Delayed/incomplete billing | Misses unreported/external spend | Labeled downward-only ceiling; preserve local debits; no balance authority claim | Open live gate |
| Concurrent replacement | Replenishes spent credit | Atomic min under memory lock/fresh Table ETag with cycle binding | Planned |
| Wrong/shared resource scope | Attributes unrelated cost or double-counts | Explicit unique membership, response resource/currency validation | Planned |
| Malicious pagination/response | Token disclosure or unbounded work | Fixed ARM origin/path/version, response/page/row/time bounds, no redirects/proxies | Planned |
| Provider outage | Cleanup starvation | Ownership/reaper independent of provider fetch; preserved estimates | Planned |
| Missing Azure read access | No live cost evidence | Operator permissions and bounded read-only acceptance before enablement | Open live gate |
