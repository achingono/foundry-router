# CI lint compatibility plan

Status: Implemented after independent plan review; final review and remote CI are pending.

CI installs Ruff 0.17.6 and reports three simplification errors in existing code, while the local Ruff 0.16.4 passed. The affected code is the two async HTTP probe context-manager blocks in `scripts/quality/openrouter_direct_probe.py` and the fake Table client delete branch in `tests/unit/test_state.py`.

Combine each HTTP client and response stream context into one parenthesized async-with statement inside the existing timeout, preserving entry order, timeout scope, streaming bounds, exception handling and reverse cleanup order. Combine the fake-client delete operation/key-presence condition. Do not change runtime source, image inputs, test assertions, dependencies or workflow behavior.

Verify using the CI Ruff version, existing focused probe and Table tests, full lint/format checks and Mypy. The already completed runtime, coverage and Docker verification remains applicable because runtime/build inputs are unchanged. Remote CI will rerun on the updated PR. Independently review the final diff and all outgoing public content before pushing.
