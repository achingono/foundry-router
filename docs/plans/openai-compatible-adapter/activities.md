# OpenAI-Compatible Adapter Extraction Activities

1. **Create `openai_compatible.py`.** Move, without semantic change: top-level/finish-reason
   allow-lists, stream bounds, `_rejection`, `_extract_text`, `_split_sse_event`, Responses and
   embeddings validation, Chat Completions request assembly, success/embeddings translation,
   `translate_error`, `extract_usage`, and the full stream decoder.
2. **Define hooks.** `OpenAICompatibleAdapter` exposes `request_context(body)`,
   `permits(body, context)`, `build_messages(body, context, *, deadline)` and
   `translate_calls(raw, context, *, completed, refusal)`; the base raises
   `NotImplementedError` for the context/message/call hooks so no provider silently gets a
   permissive default. `OpenAICompatibleStreamDecoder` takes a required `context` and exposes
   `_translate_calls(raw, *, completed, refusal)`. `stream_decoder_class` selects the decoder.
3. **Provider label.** Class attribute `provider_label` interpolated into every message that
   currently says "Google", so public 422 texts and internal errors stay identical.
4. **Reduce the Google module** to `GoogleStreamDecoder(OpenAICompatibleStreamDecoder)` with the
   empty-profile default context, and `GoogleAiStudioAdapter(OpenAICompatibleAdapter)` with the
   profile constructor and `google_tools` hook implementations. Keep the vendor docstring and
   re-export `MAX_GOOGLE_*` aliases.
   Preserved subclass surface (names and semantics unchanged, no `__slots__` so forwarding can
   set `prefetch_finished`; `finish_at_prefetch_eof` duck typing untouched): adapter
   `_check_responses_request`, `_check_feature_request`, `_translate_responses_success`,
   `_translate_embeddings_success`; decoder `_context`, `_call_fragments`, `_call_ids`,
   `_text_parts`, `_item_id`, `_message_index`, `_archived_messages`, `_input_tokens`,
   `_output_tokens`, `_finish_reason`, `_buffer`, `_validated`, `_sse`, `_next_sequence`,
   `_open_message`, `_absorb_calls`, `_handle_payload`, `_handle_provider_event`,
   `_terminal_events`, `feed`, `finish`, `build_failure`, `usage`, `validated`.
   `GoogleStreamDecoder` keeps its optional `context` (empty-profile default) and every
   Google `create_stream_decoder` passes context explicitly.
5. **Tests.** Keep all existing tests unchanged. Add focused tests for the new module:
   base hooks fail closed, label interpolation, and a minimal text-only subclass round trip
   (non-streaming and streaming) proving the base is reusable without Google imports.
6. **Docs.** Update architecture/solution-structure descriptions of `api/adapters/` and this
   plan's evidence.
7. **Verify.** Focused Google suites, full suite with coverage ≥ 80%, Ruff check/format, mypy,
   link check and `git diff --check`. Docker build if available.
