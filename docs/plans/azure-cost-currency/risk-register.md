# Currency Risks

| Risk | Mitigation |
| --- | --- |
| Wrong rate direction or currency | Exact subscription mapping and CAD-per-USD division |
| Stale/malformed public data | Fixed endpoint/date/type/size/deadline; fail closed |
| Overstated ceiling | Decimal upward-cost/downward-ceiling rounding, min application |
| Misleading transaction-day FX claim | Latest-rate operational estimate explicitly documented |
| Credential or billing leakage | Safe fixed evidence only, no raw costs/IDs/errors |
