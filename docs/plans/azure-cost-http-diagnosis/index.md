# Bounded Azure billing HTTP diagnosis

**Implemented locally**, single live diagnosis recorded (billing 429), 2026-10-09 UTC (2026-10-08 Toronto). The reviewed subscription CAD
acceptance returned a provider-boundary HTTP rejection in 6.129 seconds, without a status
code or accepted ceilings. This phase diagnoses the existing read-only query contract; it
does not retry the consumed invocation or weaken currency/completeness checks.

After independent review, add a verifier-only transport observer to the existing CAD
acceptance preparation/provider. One new immutable invocation, two bounded account metadata
discoveries, one public rate snapshot and one complete refresh (at most two configured groups,
existing ten-page/group and 30-second overall bounds). No transport retries, added billing
probes, grants, deployment, balance application or production change. Stop on normal first
provider failure. Use a new durable started/result pair and OS lock; replay/interruption
refuses further external work. Preserve all prior results.

Observe HTTP response headers only, before returning the same response/stream to the normal
provider. Bind the request's exact resource filter set to one configured group. Record only
safe group label, consecutive page index, integer status in 100..599 and Retry-After
classification absent/seconds/invalid. Accept only ASCII integer seconds of at most six
digits and <=86,400; treat duplicate Retry-After headers as invalid; omit all invalid raw values. Do not follow Retry-After or automatically
rerun. No body reads, status reason, URLs, error messages, identifiers, authentication or
arbitrary header keys/values enter evidence. Validate exact record fields and bounds before
atomic finalization under the invocation lock. Close the underlying transport with provider
ownership. Success remains accepted only through the unchanged runtime parser.

Test exact query binding, rejected headers, unexpected record keys/status/pages, unchanged
stream/no reads on rejected responses, provider stop after HTTP failure, cleanup and consumed
invocation refusal. Run focused/full tests, lint/format/type checks and contextual review.
Verifier-only changes need no new Docker image. Record proven status only: 429 proves query
throttling for that response, 401/403 proves rejection rather than a complete permission
analysis, other statuses retain unknown cause. Do not infer timing from invalid headers.
Commit plan, implementation and one execution outcome as separate phase transitions.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
