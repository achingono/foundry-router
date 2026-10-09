# Envelope evidence

Five provider 200/public 502 cases are preserved in the prior stage. One reviewed project-2 diagnostic dispatch is now recorded in
diagnostic result (local-only `diagnostic-result.json`). Provider returned 200, public 502, with 7 input/
2 completion tokens; synthetic $0.009 debit matched and reservations cleared. Safe schema
flags identify a nonempty message `extra_content` object, which the text-only adapter rejects.
No arbitrary keys or provider-state values were recorded. This establishes the rejection
boundary, not the nested semantics. The reviewed repair allows inert/null metadata only;
nonempty state does not qualify and was not silently discarded. Compatibility enablement
remains gated on a separately reviewed exact provider-state contract if required by clients.
The diagnostic reserve remains consumed; no repeat of this case is permitted.

- Independent plan review cleared the one-call structural-only contract.
- Ten diagnostic tests passed with 91.41% observer coverage; combined compatibility tests pass.
- Persisted identity/schema/ledger validation fixes the review finding and refuses corruption.
- Ruff/format/strict mypy pass; full suite 1,804 passed, 3 platform skips, 18 deselected, 89.67% coverage. No runtime adapter change. Independent final review cleared all material findings, with 37 combined cases passing.

Follow-up wrapper result (local-only `wrapper-result.json`): one project-3 nonstream diagnostic identified
exact extra_content.google.thought_signature nonempty string, small lengthclass, unknown counts0.
Provider200/public502, observed7input/1completion, $0.008 synthetic debit matched, cleanup/nooverrun.
No signature bytes retained. Operator requires Responses; a separate concrete stateless signature
policy is under review before any runtime repair.
