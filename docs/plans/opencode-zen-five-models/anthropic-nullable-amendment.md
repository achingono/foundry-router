# Anthropic absent optional response metadata

Status: Planned pending independent approval.

The seven-case nonstream-Gemini staging run passed both Gemini models. Sonnet native Messages returnedHTTP200, but translation rejected it (public502), with known estimated0.000112USD debit. Exact native output was never logged. Current public Anthropic SDK Message defines nullable container, diagnostics, stop_details; TextBlock defines nullable citations. Their names are missing from the adapter's closed response allowlist, so absent optional metadata is a plausible incompatibility.

Accept only these documented absent forms: container/diagnostics/stop_details absent or null; text citations absent/null/empty list. Validate and omit them, retaining rejection of non-null container/diagnostics/stop-details, nonempty citations, unknown fields and unsupported content. Preserve cache-inclusive actual usage even when conversion rejects. This does not add tools, containers, cached continuation, citation rendering or streaming. Add tests for all absent/empty forms and invalid/non-null metadata across actual forwarding settlement. Native request/auth/header mapping remains unchanged.

Also address the already-reviewed nonblocking timestamp-offset suggestion while rebuilding: constrain offset hours/minutes explicitly, with malformed-offset regression tests. No other runtime scope expansion.

The halted stage is stopped and its measuredremaining0.089183USD derives from0.09 minus0.000453/0.000252/0.000112. Add one fixed fourteen-case identity `opencode-zen-five-20261013-anthropic-nullable`, conservative staging0.088USD (discard0.001183), production9.90USD unchanged. Same Gemini/Sonnet nonstream policies, requestbounds512/128, Grok/Muse both512, prices/reserve. Preserve all four prior manifests/ledgers and diagnostic. Require complete historical validation including the latesttwo passed/thirdfailed prefix, latest zero-reservations/stopped snapshot and exact debit/floor accounting. No replay/replenishment/refund/transfer. New image/fullverification/independent code+packet review before seven fresh stage calls; same production handoff/acceptance/rejection gates.

Sources read October13: public anthropic-sdk-python main `types/message.py` and `types/text_block.py`; field-name cause remains unproven until live acceptance.
