# Public runtime release evidence

| Check | Observed result |
| --- | --- |
| Reviewed runtime equivalence | All 80 runtime files match the reviewed committed source exactly |
| Docker build inputs | Dockerfile, package configuration, README and Docker ignore rules match the reviewed inputs exactly |
| Focused regression suite | 209 passed |
| Full synthetic unit/integration suite | 3,454 passed, 3 skipped, 20 Docker/Azurite tests deselected; 90.58% runtime coverage |
| Local Table emulator | 15 passed; combined runtime coverage 90.76% |
| Ruff lint and formatting | Passed; 1,178 files already formatted |
| Mypy | Passed for all 80 runtime source files |
| Docker build | Passed with normal package access; an initial offline build failed on an uncached package-install layer |
| Docker/Linux acceptance | 2 passed: real native/translated intake children with network disabled, and owned-container loopback liveness |
| Relative documentation links | Changed documents pass; repository-wide inspection found 43 inherited broken links in historical public documentation, with none introduced |
| Diff whitespace and targeted private-data/dependency scan | Passed; no new private path, account/resource identity or excluded helper dependency found |
| SonarQube script | Absent from this repository; no scan claimed |
| Final independent candidate review | Required before publication; pending at freeze |

Local Python tests used Python 3.14; the Docker runtime uses Python 3.12. Deprecation warnings and existing optional-test skips remain visible in test output. The Docker/Linux fixture explicitly does not establish maximum request capacity. No Azure requests, image publication, application deployment, provider inference or scale acceptance occurred in this preparation.

Optional Azure intake and completion observations remain disabled by default. Deployment gates are documented in [production maintenance](../../operations/production-deployment.md); local verification does not establish provider limits, full-runtime maximum/concurrent capacity, destination ingestion, alerts or multi-worker scale readiness.
