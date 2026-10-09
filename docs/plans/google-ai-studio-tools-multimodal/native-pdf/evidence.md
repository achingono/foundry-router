# Native/PDF evidence

**Partially implemented**. Templates copied before drafting; native contract independently
reviewed before runtime edits. Official document/compatibility/native references fetched2026-10-05.
PDF worker/resource/accounting design remains a separate gate; no PDF/live support claimed.

Native foundation:32 unit and10 HTTP tests pass, including actual OpenAI Python2.8.1 streamed
call/text/call accumulation and full-history replay, final item-status consistency, cumulative
usage, fixed transport and conservative billing for malformed output/late usage/duplicate JSON.
Independent deep review on2026-10-05 resolved all Critical/Major findings. The parser retains
strict envelope/content/candidate allowlists, bounded raw decoding and4MiB aggregate output.
Native media validation executes one decode pass per adapter check/build.

Native mixed benchmark (local-only `measurements/native-mixed.json`):8 concurrent callers×100 requests;
941.97ms maximum event-loop delay,488.39ms maximum intake,37,404,672 bytes incremental peak RSS.
All predeclared gates passed; local macOS/Python3.14 evidence only, with limited loop-delay margin.
Final native verification:711 passed,15 deselected,87.78% full coverage; Ruff check/format
and mypy passed. Docker rebuilt after final status fixes; Python3.12.15 ordered native
item-status synthetic smoke passed. Sonar script absent. Isolated local Azurite restarted:
14 actual distributed-state tests passed; no Azure production traffic.
Combined full/Azurite coverage88.41%. Runtime changes do not enable production profiles.
240 changed/new relative documentation links resolved; diff whitespace check passed.

## Separate PDF design review

[PDF preparation contract](pdf-design.md) independently reviewed2026-10-05. Design findings
resolved: verified page-tree parent backedges, repeated stream/font expansion, separate native
text ceiling, pre-reader classic xref/span validation, finite raw text operator grammar,
incremental bounded stdout, atomic worker slots, honest inherited I/O capabilities/import effects
and aggregate parent/child RSS measurement. No remaining Critical/Major design findings; approval
requires implementation to honor these exact bounds and a separate implementation deep review.
pypdf6.19.0 reviewed and installed; BSD-3-Clause, Python>=3.9,
no required dependency on Python3.12/3.14.

## PDF runtime in progress

**Partially implemented**: finite raw tokenizer/classic xref/stream spans/text operators,
page ownership/parent backedges, shared verified resources, immutable preparation and explicit
adapter/routing/failover/forwarding metadata flow. Default-off native-only profiles require
visual/native-text token ceilings; conservative pool-wide per-document admission estimates.
Inline user `input_file` maps unchanged data to native inlineData; Azure file input retains
existing pass-through behavior. No file upload/retrieval/rendering/transcoding.

First independent implementation review found and corrected CR comment divergence, global
Azure interception, shared-resource inheritance, snapshot digest timing, repeated cancellation,
pipe overflow cleanup and readiness gaps. Raw objects are compared with pypdf interpretations;
dependency warnings reject. Final independent review remains pending; do not enable PDFs yet.

Linux worker smoke passed with actual CPU/address-space/file/fd limits. Local macOS27 rejects
RLIMIT_AS setup; PDF readiness is Linux-only and fails closed on this host. Readiness checks
pinned dependency and a cached bounded worker self-test; worker infrastructure failure returns503.
Parser/lifecycle/HTTP tests are expanding; final full coverage/build gates remain pending.
Initial Linux benchmark at8 callers/80 attempts:20 accepted and60 immediate slot-saturation
rejections. Simple4page:85,200,896 incremental aggregate RSS,209.40ms max intake.64KiB4page:
85,262,336 incremental aggregate RSS,207.60ms max intake.64KiB invalid:40,574,976 incremental
aggregate RSS,114.96ms max intake. These preliminary runs passed declared RSS/deadline gates;
final mixed/max-work/current-code measurements and container peak are still required.

Independent runtime re-review passed after all findings were corrected:78 focused tests passed,
one actual Linux-worker test skipped on macOS. Per-node parent declarations cannot hide forbidden
resources/geometry through child overrides. No remaining Critical/Major runtime findings; final
resource/full/client/live gates remain open. Facts bind the pre-await snapshot, cleanup shields
reap against repeated cancellation, and readiness shares the same two process-wide worker slots.
Current full local suite:789 passed,1 Linux-worker skip,15 deselected,87.87% coverage.
New parser/preparer/worker modules each exceed80% coverage; Ruff check/format and mypy pass.
242 relative links resolve and final diff whitespace check passes. Current-code Docker build
passed, with real Linux readiness/valid/invalid/reap smoke. Current64KiB4page benchmark (local-only `measurements/pdf-maximum-preliminary.json`)
passed:85,585,920 incremental aggregate RSS,142,155,776 peak aggregate RSS,204.73ms max intake,
3.27ms max loop delay. This fixture is maximum bytes/pages with padding, not maximum parser work;
mixed/max-work/current-code invalid resource and actual Linux client/lifecycle gates remain open.

Operator supplied a Key Vault credential reference on2026-10-05. No secret values were read or
logged. Operator confirmed each key belongs to a separate free-tier project, with default spend
limits. Proposed isolated ceiling:20 requests/20,000 total tokens per project, zero paid spend;
exact model IDs remain requested. No provider calls executed.

## Completed local PDF gate

**Implemented locally**, independently re-reviewed2026-10-05 with no outstanding Critical/Major
findings. The content operator budget is2048 aggregate per document; four512operator streams
pass and four513operator streams reject. Aggregate128KiB/four-document/four-page bounds and
lower candidate caps are tested. Three separate synthetic quota projects prove lower-page-cap
exclusion before admission and429failover without reparsing or changed inline content.

Actual Python3.12.15 Linux PDF unit/HTTP tests:92 passed, including the real isolated worker
through authenticated HTTP preparation, reservation, native mock transport, failover and cleanup.
Provider responses remain synthetic. The actual OpenAI2.8.1 streamed PDF/tool/schema replay fixture
uses mocked preparation/provider responses; it verifies public serialization/order and separate billing.
Full local suite:801 passed,2 Linux-only skips,15 deselected,87.95% coverage. Ruff check/format and
mypy pass. Current runtime Docker build passed; Linux limits/import setup and cleanup exercised.
CPU/address-space limits are enforced, not measured per-worker CPU maxima. No live support claimed.

Final full-path measurements include bounded JSON intake, real worker preparation, candidate
selection/quota admission, adaptation, encoding and cleanup;8 callers×100 attempts each. Two
no-queue worker slots yield200 inspected requests and600 immediate capacity rejections per run,
not eight simultaneously admitted parsers. All configured wall/intake/loop/RSS gates passed:

| Workload | Incremental aggregate RSS bytes | Peak aggregate RSS bytes | Maximum intake ms | Maximum loop delay ms |
| --- | --- | --- | --- | --- |
| Mixed (local-only `measurements/pdf-fullpath-mixed.json`):65534-byte four-page PDF,2048 operators, four384-square PNGs | 120946688 | 189972480 | 248.29 | 18.19 |
| Aggregate (local-only `measurements/pdf-fullpath-aggregate.json`):two blank one-page PDFs,131072 bytes total | 106455040 | 174968832 | 470.60 | 18.06 |
| Late-invalid (local-only `measurements/pdf-fullpath-work-invalid.json`):final unsupported operator after preceding streams | 75091968 | 143593472 | 135.94 | 19.32 |

The invalid run has zero admitted-valid requests and200 inspected-invalid rejections. Cgroup peak
is recorded separately in each artifact and stays below512MiB. Earlier measurements above are
preliminary narrower fixtures. These runs do not establish every possible maximum combination.
Exact configured model IDs, document text-token/pricing evidence and live compatibility remain
operator gates before enabling PDF profiles. Production configuration remains unchanged.
