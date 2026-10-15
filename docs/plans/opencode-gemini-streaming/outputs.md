# Gemini streaming Outputs

## Mandatory Outputs

| Output | Description | Format |
|---|---|---|
| Diagnostic implementation and approval | Offline mocked framing/bounds/redaction/crash/replay tests; independent code + concrete funding/artifact packet review before dispatch | Code/tests + review |
| Streaming diagnostic artifact | New identity and hashes, exclusive durable consumption before egress, permanent D debit, bounded allowlisted result; missing result remains consumed | Private immutable JSON, file/directory fsynced |
| Adapter correction (only if proven) | Bounded streaming-envelope fix in `google_native.py` + regression tests | Code + tests |
| Acceptance harness and policy packet | Recognized eighteen-slot identity, nine ordered cases per environment; both Gemini streaming-enabled; fixed S <= R-D; complete historical bindings | Code/tests + immutable manifest/private config |
| Verification record | Focused/full pytest, coverage, Ruff, mypy, Docker build, deep review | Evidence log |
| Staging re-qualification | Nine cases including both Gemini streams on the final image, exact usage/debit, stopped writer and zero reservations | Manifest/ledger/proof |
| Production release and acceptance | Updated nine-case policy, fresh immutable inherited handoff, same image and fixed OpenCode 9.90 seed; actual execution evidence under inherited procedure | Reviewed packet and subsequent evidence |

## Optional Outputs
- Documented negative result (cause not established or qualification failed); production remains blocked by streaming-first, with no automatic nonstream fallback.

## Output Quality Checklist
- [ ] All mandatory outputs produced
- [ ] All outputs reviewed before gate
- [ ] Evidence log updated with output references
- [ ] No prompts/outputs/credentials in redacted outputs
