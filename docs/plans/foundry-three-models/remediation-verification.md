# MAI compatibility remediation verification

**Status:** Local compatibility amendment verification completed. The later replacement release, fresh accounting handoff, new public MAI acceptance and ingress restoration are recorded in [production evidence](production-evidence.md). This document records the local gates and synthetic worker checks only.

## Scoped behavior verified

- The PNG inspector and `OutputInspectionLease` keep `allow_c2pa=False` by default. The Responses route enables the profile only for a configured `azure_mai` pool. Existing Google image inspection therefore retains its default strict behavior.
- The Linux worker accepts only its default invocation or the server-owned `--mai-c2pa` flag. An unknown flag returned exit code 2 in the final image.
- Default inspection rejected a synthetic PNG containing a CRC-valid `caBX` chunk. A read-only-mounted smoke ran an `allow_c2pa=True` inspection lease in the final image and passed. Its decoded-byte count and digest matched the complete original PNG bytes, including the opaque chunk. The worker does not parse or authenticate the chunk, so provenance authenticity is not established.
- MAI accepts extra upstream envelope fields but still requires one bounded canonical base64 PNG item. Provider usage is ignored for billing; adapter usage remains unknown and the public response does not fabricate token counts.
- Configuration and operational documentation describe the profile as MAI-only, the provenance as opaque, usage as unverified for billing, and the default Google profile as strict. Existing raster, compressed-data expansion, byte, chunk-count and CRC checks remain in place.

## Measured gates

- Focused final modules: `.venv/bin/python -m pytest tests/unit/test_google_output_png.py tests/unit/test_google_output_work.py tests/unit/test_foundry_translated_models.py -q` — **99 passed, 1 skipped**.
- Full remediation run: `.venv/bin/python -m pytest tests/unit/ tests/integration/ -m "not docker and not azurite" --cov=src/foundry_router --cov-report=term-missing --cov-fail-under=80` — **2,867 passed, 3 skipped, 19 deselected**; measured `src/foundry_router` coverage **90.41%** (above 80%).
- Ruff check passed. `.venv/bin/python -m ruff format --check .` passed; **1,047 files already formatted**. `.venv/bin/python -m mypy src/` passed with **76 source files** and no issues.
- The final `foundry-router:mai-compat` Docker image build completed successfully. A temporary container ran with synthetic Anthropic and MAI endpoints and local estimate configuration. `/health/live` and `/health/ready` both returned HTTP 200; readiness was true and every reported check was true.
- Linux/amd64 worker smoke ran on `x86_64` inside Docker. The supplied script passed byte/digest preservation for the MAI profile and rejection by the default profile. A separate unknown-worker-flag invocation returned exit code 2 as expected. The Docker host is ARM64, so the Linux/amd64 image ran under local translation. The temporary container was stopped and removed.
- SonarQube is **not applicable** because `scripts/quality/sonarqube-scan.sh` is absent; no scan pass is claimed. Azurite was not run: this amendment changes only PNG parsing/worker invocation and does not change Table schema or Table-specific code.

## Documentation, limits and release boundary

The original review checked 153 relative links across 22 changed/new Markdown files; no missing targets were found. The final documentation audit and status-claim review are recorded in [final verification](final-verification.md). This evidence distinguishes synthetic local worker checks from the later live acceptance recorded in [production evidence](production-evidence.md). The review confirms opaque-provenance and unknown-usage wording. The implementation uses the user-approved **USD 1 per image request local estimate**; this is not an authoritative Azure charge or a guaranteed billing ceiling.

No provider request, production configuration or ingress change, Azure mutation, new deployment or source edit was performed during this local verification. The synthetic PNG smoke alone does not prove that an actual MAI response passes the profile; the later exact live output acceptance is documented separately in [production evidence](production-evidence.md). The consumed failed call and diagnostic liability were not replayed or refunded. See the [remediation plan](mai-remediation.md), its [independent plan review](remediation-plan-review.md), and the [production packet](production-packet.md).
