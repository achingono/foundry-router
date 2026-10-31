# Isolated Ingress Watchdog Outputs

## Mandatory Outputs

| Output | Description | Format |
|---|---|---|
| Watchdog design | Components, lease protocol, trust boundaries, timing, failure matrix, and Azure boundary assumptions | `design.md` |
| Independent design review | Verdict, findings, and disposition; reviewer did not author the design | [design-review.md](design-review.md) |
| Feasibility evidence | Official Azure ingress/IP semantics plus disposable validation of the mandatory dedicated private boundary and denial attribution | Redacted Markdown evidence |
| Implementation/deployment proposal | Only after design approval; pinned resources, identity, network, cost, rollback, and finite what-if scope | Separate future packet |

## Optional Outputs

- Candidate local proxy protocol tests; no cloud mutation or paid request.

## Output Quality Checklist

- [ ] No claim of absolute closure during Azure/platform/network failure without demonstrated enforcement.
- [ ] Separate process failure from infrastructure failure and from already-dispatched provider work.
- [ ] No secrets, prompts, model output, or unnecessary cloud identifiers in evidence.
- [ ] The rejected G1 packet remains unapproved and unexecuted.
