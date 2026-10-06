# Image-format evidence

**Implemented** local code for opt-in baseline JPEG/static lossless VP8L, with synthetic
parser/HTTP/client contracts. LargerJPEG, lossyWebP, PDF/signed/additional-media and exact-model
live verification remain **Planned**. The full parent plan remains **Partially implemented**.

| Item | Evidence | Scope |
| --- | --- | --- |
| Plan templates and review | Seven blank templates copied; independent session `review_implementation_plan` | Review before runtime changes; later entropy/work amendments reviewed before dependent edits |
| Official source | Google image understanding fetched2026-10-05 | JPEG/PNG/WebP and small-image258 tier documented; no model capability/live inference inferred |
| Strict subset | JPEG<=128 dimensions, <=32768 aggregate pixels and <=384 coded blocks/history pass; static single-chunk VP8L<=384 | PNG remains default; image_formats explicitly enables other formats |
| Parser tests |39 tests | Format/type/container/resource bounds; JPEG entropy completeness, EOI truncation, short/long codes, stuffing/restart/padding, run overflow; native bounded raster load |
| HTTP image billing tests |4 new known/missing-usage cases plus14 feature lifecycle regressions | Ordered JPEG/VP8L/schema mapping, one dispatch, billable validation failure and released inflight credit |
| Full suite |669 passed,15 deselected,87.45% coverage | Unit/integration, excluding Docker/Azurite; image-only changes retain prior14 passing Azurite evidence |
| Lint/format/types | Ruff check/format and mypy passed |374 formatted files,35 source modules |
| Docker | Image build passed, Python3.12 syntheticJPEG/VP8L parser smoke passed | Temporary container removed; no Azure/provider traffic |
| Sonar | scripts/quality/sonarqube-scan.sh absent | Conditional scan not applicable |
| Independent deep review | No remaining Critical/Major code findings | Parser regressions/budgets and mixed/late-failure resource measurements addressed |
| Live/provider/deployment | Not run | Operator exact model/credential references/spend caps pending; production remains memory/one |

## Concurrent resource measurements

Reproduce with `.venv/bin/python scripts/quality/google-media-benchmark.py --format <format>
--workload <workload>`. Each run is8 concurrent async callers/100 requests each; actual outer
JSON intake -> adapter validation -> upstream mapping and JSON encoding, including repeated
media validation passes. RSS includes native allocations; baseline is process peak after
fixture creation. Results apply only to this local macOS arm64/Python3.14.7 process and workload,
not Azure capacity, global concurrency admission or multi-worker deployment. The2MiB body cap
and all hard aggregate limits remain unchanged. Thresholds: incremental RSS<=128MiB,
event-loop delay<=1second, each request intake<5seconds. No threshold was relaxed.

| Workload | Decoded byte cap | Body bytes | Max intake ms | Max loop delay ms | Incremental RSS bytes | Result |
| --- | --- | --- | --- | --- | --- | --- |
| PNG random384,2images |886760|1182544|236.68|446.42|38174720|Passed |
| VP8L random384,2images |884896|1180058|226.76|430.06|29949952|Passed |
| Worst entropyJPEG88,all tables |84758|113141|269.15|517.01|4505600|Passed |
| Late-invalid worstJPEG88,final marker |84758|113141|178.82|328.36|3522560|Passed |
| Eight tinyJPEGs/all8Huffman tables |9184|12840|35.72|56.82|3112960|Passed |
| Mixed worstJPEG88+randomPNG384+VP8L384 |970586|1294378|545.02|996.22|31145984|Passed, small delay margin |
| Eight compressed mixed images/worstJPEG |88831|119037|296.71|568.51|6684672|Passed |
| Invalid maximum-size signature |1048576|1398298|188.74|354.11|29802496|Passed |

The initial768-block worstJPEG128 experiment failed1second scheduling (1104.95ms isolated).
The384-block budget is the final implementation. LargerJPEG is not enabled. The entropy
validator checks bounded syntax/completeness; valid changed pixels cannot be detected as
corruption. LossyVP8 remains disabled because native loading tolerated a short tail cut.
The mixed run's small scheduling margin is a limitation. Its isolated follow-up passed with
488.05ms max intake,942.88ms max scheduling delay and26083328 incremental RSS bytes.
[Raw measurement artifacts](measurements/mixed-isolated.json) preserve exact local scope.
Normal128-square JPEG passed126.91ms intake/235.51ms scheduling and1294336 incremental RSS.
The entropy helper reached95.14% coverage in the full suite.
