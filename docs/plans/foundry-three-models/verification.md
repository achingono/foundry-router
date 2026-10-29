# Verification evidence

**Status:** Historical local implementation verification for the initial release. The replacement release, public acceptance and restored intake are recorded in [final production evidence](production-evidence.md); Azure billing beyond configured local router estimates remains unverified.

## Tests and static checks

- Focused: `.venv/bin/python -m pytest tests/unit/test_foundry_translated_models.py -q` — **45 passed**.
- Full CI-applicable suite: `tests/unit/` and `tests/integration/`, excluding `docker` and `azurite` markers — **2,850 passed, 3 skipped, 19 deselected**. Measured coverage for `src/foundry_router`: **90.42%**, above the 80% requirement. The full-suite run preceded a formatting-only pass; the focused test file and all static checks below were run against the final source.
- Ruff: `.venv/bin/python -m ruff check .` — passed.
- Format: `.venv/bin/python -m ruff format --check .` — passed; 1,039 files already formatted.
- Types: `.venv/bin/python -m mypy src/` — passed; 76 source files, no issues.
- SonarQube: `scripts/quality/sonarqube-scan.sh` is absent, so this gate is **not applicable**; no scan result is claimed.
- Relative documentation links: **136 checked across 14 changed/new Markdown files; no missing targets**. `git diff --check` passed. No Table schema or Table-specific code changed, so Azurite tests were not applicable to this candidate.

## Built-image and Linux worker smoke

The `foundry-router:three-models` Docker image built successfully. A temporary container used synthetic `azure_anthropic` and `azure_mai` backend/model registrations, synthetic credentials, and user-approved local pricing estimates. No requests were sent to either synthetic provider endpoint.

- `GET /health/live` — HTTP 200, `{"status":"alive"}`.
- `GET /health/ready` — HTTP 200, `ready=true`; configuration, backend/model registration, authentication, credit configuration, pricing completeness and rate-limit share checks all returned true.
- The Linux PNG worker smoke passed inside the image on `x86_64`: 3,129 encoded bytes, 3,146,752 expanded bytes, digest verified. The Docker host is ARM64; Docker reported the architecture mismatch and ran the image's x86_64 environment under local translation.
- The temporary container was stopped and removed after the checks.

The smoke used the user-approved local Sonnet estimates of **USD 4/M input and USD 10/M output tokens** and the MAI estimate of **USD 1 per image request**. These are local router estimates, not verified Azure charges or a guaranteed billing ceiling. See [pricing evidence](pricing-evidence.md) for the exact retail meters and unresolved billing dimensions. No live provider request, Azure mutation, production deployment, ingress change or model-pool activation was performed.

## Review and remaining acceptance

The independent [implementation review](implementation-review.md) found no Critical or Major code issues. At the time of this local verification, production registration and provider acceptance had not yet occurred. Subsequent production results are recorded in [final production evidence](production-evidence.md). The unrelated `responses-request-limit` plan was not edited.

The local tests and worker fixture do not establish that a real MAI PNG passes the inspector, nor do they establish Azure Foundry's exact Anthropic charge, a fixed MAI image charge, or a Terra Global Priority price. The live MAI result and its bounded inspection are documented separately in [final production evidence](production-evidence.md). Configured local estimates are not authoritative Azure charges or balances. No local smoke result should be described as production deployment or live provider validation.
