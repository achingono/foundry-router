# Evidence

**Partially implemented**, 2026-10-06. Independent design/runtime review found no Critical or
Major issue. Exact-model live support remains unverified; audio is default-off.

Finite PCM WAV parsing, immutable prepared facts, candidate revalidation, native mapping and
MIME-specific accounting are implemented. Required pricing/TPM affirmations and native-only
pools reject unsafe configurations. Azure-only file forwarding is preserved. No codec, upload,
transcoding or URL fetching is added.

26 parser/configuration tests and 10 HTTP regressions pass. Pinned OpenAI 2.8.1 create/stream,
ordered audio/text, full-history replay, audio/PDF combination with mocked PDF inspection,
three-project lower-cap exclusion and 429 failover, free TPM admission and paid known/missing
usage settlement on unsupported output are covered with synthetic transport. These tests do not
establish live Google support, process restart or real TCP disconnect behavior.

Linux maximum workload (local-only `measurements/audio-http-linux-max.json`): 8 callers × 100 requests,
2 files / 640088 decoded bytes / 320000 frames; alternating stream/nonstream; network disabled,
512 MiB / 2 CPU. All 800 returned 200; observed sampled incremental RSS 50216960 bytes, maximum loop delay
48.45 ms and request latency 55.77 ms. This is audio-only full HTTP evidence. An earlier macOS
harness supplied JSON for upstream streaming and is not qualifying resource evidence.

Final audio checkpoint: 1110 passed, 2 Linux-only skips, 15 Docker/Azurite deselections,
88.91% coverage; whole-tree Ruff/format, mypy and Python 3.12 Docker build pass.
Docker health and 173 relative documentation links pass; further final documentation links and further incremental gates remain required. Sonar script absent.

Remaining: combined media/state resource and cancellation gates, additional combinations,
final deep review/quality/docs and exact model/pricing/quota/live evidence before operator
opt-in. Signed startup gate is unchanged. Production is unchanged.

Two direct ASGI blocked-send tests now pass: response-start/body timeout closes upstream,
settles known $0.00055 and input40/RPM1 once with real in-memory stores. This is not real TCP
cancellation or distributed exactly-once proof. Combination test now enables both features
before rejecting their missing exact combination.

Combined actual PDF-worker/audio measurement (local-only `measurements/audio-pdf-http-linux.json`) uses
2 maximum WAVs plus one deterministic four-page PDF (not maximum PDF bytes), 8×100 alternating
stream/nonstream in network-disabled 512MiB/2CPU Linux: 28 successful,772 preadmission503,
zero502; observed sampled RSS growth17694720B; loop45.92ms/request381.54ms. PDF-worker two-slot
capacity bounds contention. This does not prove full media/state/wire maxima. Parent goal remains
incomplete. Live model selection now authorized as all supported models discovered perproject;
20requests/20000tokens/project and zero paidspend remain caps, no live inference yet.
