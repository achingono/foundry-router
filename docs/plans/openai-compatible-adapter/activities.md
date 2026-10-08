# OpenAI-Compatible Adapter Extraction Activities

1. **Characterize the baseline before extraction.** Add fixtures/tests against the current
   Google adapter, freezing UUID generation and time so complete outputs are deterministic.
   Capture complete `AdapterRejection` objects (status, code and message), upstream request
   bodies, translated Responses/embeddings bodies and ordered SSE bytes. Cover text success,
   tools (including parallel calls), structured text, refusal, incomplete output, usage-only
   chunks, missing usage and failure termination; include native ordered text/tool segments
   and signed/audio lifecycle cases where they use the preserved surface. Exercise split
   UTF-8/delimiters and multiple events per chunk. Record the pre-extraction run and retain
   the same expected fixtures after extraction; do not regenerate them from the new code.
2. **Create `openai_compatible.py`.** Move, without semantic change: top-level/finish-reason
   allow-lists, stream bounds, `_rejection`, `_extract_text`, `_split_sse_event`, Responses and
   embeddings validation, Chat Completions request assembly, success/embeddings translation,
   `translate_error`, `extract_usage`, and the full stream decoder.
3. **Define hooks and concrete context typing.** `OpenAICompatibleAdapter` exposes `request_context(body)`,
   `permits(body, context)`, `build_messages(body, context, *, deadline)` and
   `translate_calls(raw, context, *, completed, refusal)`; the base raises
   `NotImplementedError` for the context/permission/message/call hooks so no provider silently gets a
   permissive default. `OpenAICompatibleStreamDecoder` takes a required `context` and exposes
   `_translate_calls(raw, *, completed, refusal)`. `stream_decoder_class` selects the decoder
   through a constructor contract accepting the adapter's context type.
   Define `ChatRequestContext` with read-only properties `tools: dict[str, dict[str, Any]]`,
   `choice: Any`, `parallel: bool`, `text_format: dict[str, Any] | None`, `max_calls: int`,
   `max_argument_bytes: int`, plus the method `validate_text(text: str, *, completed: bool,
   has_calls: bool) -> None`. Read-only properties permit the existing frozen dataclass to
   satisfy the protocol without changing its fields. Parameterize both bases with a context
   type bounded by this protocol; hook parameters/returns, decoder construction and `_context`
   use that type. Specialize both Google subclasses with `GoogleRequestContext`, so unchanged
   native `_context.validate_arguments()` calls and Google `translate_calls` retain concrete
   typing. Google-only argument/call validation methods remain outside the shared protocol.
   Verify the Google context satisfies the protocol and the minimal text-only context needs
   no Google-only methods under strict mypy.
4. **Provider label.** Class attribute `provider_label` interpolated into every message that
   currently says "Google", so public 422 texts and internal errors stay identical.
5. **Reduce the Google module** to
   `GoogleStreamDecoder(OpenAICompatibleStreamDecoder[GoogleRequestContext])` with the
   empty-profile default context, and
   `GoogleAiStudioAdapter(OpenAICompatibleAdapter[GoogleRequestContext])` with the profile
   constructor and `google_tools` hook implementations. Keep the vendor docstring and
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
6. **Tests.** Keep all existing tests and the pre-extraction characterization fixtures unchanged.
   Assert exact Google rejection objects and exact deterministic response/event outputs, not
   only status codes, event presence or successful SDK consumption. Add focused tests for the new module:
   base hooks fail closed, label interpolation, and a minimal text-only subclass round trip
   (non-streaming and streaming) proving the base is reusable without direct runtime Google imports.
   The import gate applies to `openai_compatible.py`, not transitive package initialization.
   Preserve the existing `ProviderAdapter` media signatures: a `TYPE_CHECKING` import of
   `PreparedGoogleMedia` from `api.google_pdf` is the sole allowed Google import in the generic
   module and is used only in annotations. No Google helper/profile/media code runs there.
   Verify package exports and backward-compatible Google class/constant imports.
7. **Docs.** Update architecture/solution-structure descriptions of `api/adapters/` and this
   plan's evidence.
8. **Verify.** Baseline characterization before extraction, then unchanged characterization
   and focused Google suites after extraction; full suite with coverage ≥ 80%, Ruff check/format, mypy,
   link check and `git diff --check`. Docker build if available.
