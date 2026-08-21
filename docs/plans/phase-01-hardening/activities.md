# Phase 01 Hardening Activities

## Step-By-Step Activities
1. Add package metadata and a supported development extra required for clean installs and Docker builds.
2. Strengthen configuration parsing with strict container and string validation, finite numeric checks, duplicate-key checks, support zero-cost pricing where valid, and make the dotenv example portable.
3. Define the backend target as an exact configured HTTPS origin plus configured path prefix, reject userinfo/alternate ports, disable redirects, and test every URL component.
4. Preserve header stripping, reject credential-bearing request kwargs, and ensure configured backend credentials are never exposed by the client boundary.
5. Remove raw exception details from logs, validate caller correlation IDs, and clear correlation context in all success and failure paths.
6. Add tests for actual serialized exception logs, nested redaction, context isolation, lifecycle cleanup, and request-target validation.
7. Make integration and Docker tests use valid, isolated synthetic configuration and ensure Docker CI supplies the same no-upstream-call smoke-test configuration.
8. Replace placeholder/permissive tests with explicit Phase 1 contract assertions and isolate global client, logging, environment, and context state.
9. Enforce the documented combined-suite coverage threshold and resolve Ruff/type/format violations.
10. Update ADRs, requirements traceability, status/structure documentation, phase evidence, and implementation-status documentation with verified results only.
11. Run focused tests, full tests, coverage, Ruff, Mypy, package installation, and Docker verification where available.

## Review Focus
- No user-controlled URL can bypass the exact configured backend origin/path boundary, and redirects cannot escape it.
- Development dependencies install using the same command used by CI.
- No exception or request context can expose credentials, prompts, outputs, or stale request IDs.
- Example configuration and CI smoke tests are runnable from a clean checkout.
- Tests assert actual behavior rather than accepting placeholders or multiple incompatible outcomes.
