# Phase 08 Evidence

## Evidence Log

| Item | Reference | Notes |
| --- | --- | --- |
| Deep-review findings source | F1–F8 in [inputs.md](inputs.md) | Work-item origin for this phase |
| F1 concurrent duplicate-ID test | `tests/unit/test_main.py::TestOpenAIEndpoints::test_duplicate_client_request_id_creates_independent_reservations` | Proves two requests with an identical client `x-request-id` reserve and finalize independently; the client correlation ID is still echoed unchanged |
| F2 oversized-body tests | `tests/unit/test_api_common.py` (`test_rejects_oversized_content_length_before_reading_stream`, `test_rejects_oversized_body_without_content_length`, `test_accepts_body_within_limit`, `test_invalid_content_length_header_rejected`) | `Content-Length` and no-`Content-Length` cases, both rejected with `413` |
| F2 bounded token-estimation recursion | `tests/unit/test_credit.py::TestRequestCostEstimation::test_walk_text_chars_bounds_recursion_depth`, `test_walk_text_chars_bounds_total_char_count` | Fails closed (`-1`) past `MAX_TEXT_WALK_DEPTH` / `MAX_TEXT_WALK_CHARS` |
| F3 readiness completeness checks | `src/foundry_router/api/routes/health.py`, existing `tests/unit/test_main.py` readiness tests | Implemented as `/health/ready` checks (`backend_credit_config_complete`, `model_pricing_complete`) rather than a config-load failure; see risk register R3 |
| F4 reservation reaper tests | `tests/unit/test_credit.py::TestCreditStore` (`test_orphaned_reservation_older_than_max_age_is_reclaimed`, `test_fresh_reservation_is_untouched_by_reaper`, `test_long_running_stream_reservation_not_reaped_when_within_max_age`, `test_reaper_disabled_by_default_infinite_max_age`) | Orphan reclaimed; fresh untouched; long stream not reaped; disabled by default (`math.inf`) unless a finite max age is supplied |
| F5 Retry-After hardening test | `tests/unit/test_main.py::TestOpenAIEndpoints::test_retry_after_non_ascii_digit_returns_none` | Non-ASCII digit header (`U+0665`) returns `None` without raising |
| F6 hot-path sync decision | `src/foundry_router/credit.py` (`InMemoryCreditStore.sync_from_settings` identity fast path), `src/foundry_router/routing/__init__.py` | Per-request call retained (see risk register R5); made cheap via a settings-object-identity check instead of removed, avoiding regressions in 20+ existing routing tests |
| F7 stream usage extraction test | `tests/unit/test_main.py::TestOpenAIEndpoints::test_stream_response_uses_terminal_usage_to_finalize_charge`, `test_stream_response_parses_crlf_and_trailing_usage_payload` | Terminal usage cost unchanged; non-usage deltas are pre-filtered out via a `b"usage"` substring guard |
| F8 auth constant-work test | `tests/unit/test_auth.py::TestClientAuth::test_valid_key_at_last_position_authenticates` (plus existing second-position bearer test) | Valid key at any position authenticates; both loops evaluate all configured keys without early return |
| Full test run | `.venv/bin/python -m pytest -m "not docker" -q` | 187 passed, 1 deselected |
| Coverage report | `.venv/bin/python -m pytest -m "not docker" --cov=src/foundry_router --cov-report=term-missing` | 90.80% overall coverage (>= 80% threshold) |
| Lint / format / type | `.venv/bin/ruff check src/ tests/`, `.venv/bin/ruff format --check src/ tests/`, `.venv/bin/mypy src/` | All clean |
| SonarQube scan | N/A | `scripts/quality/sonarqube-scan.sh` does not exist in this repository |
| Deep-review prompt run | N/A | `.agents/prompts/deep-review.prompt.md` does not exist in this repository |
| Docker build | N/A | Docker CLI not available in this environment; skipped |
| Documentation updates | [requirements-traceability.md](../../decisions/requirements-traceability.md), [security.md](../../configuration/security.md), [observability.md](../../operations/observability.md), [configuration/index.md](../../configuration/index.md), [.env.example](../../../.env.example) | Traceability, security, observability, and configuration docs updated with verified behavior only |

