# Evidence

**Planned**. Profiled aggregate workload raw_json_parse40.32ms, snapshot_encode9.24ms,
loop72.42ms. No runtime edits before independent review; fullscope remains partial.

**Partially implemented**. Independent design review approved the server-owned Responses parser
offload. Original absolute deadline/byte/parser semantics are retained; immutable wire bytes
capture occurs only after shared capacity acquisition. Two-slot shielded worker owns cleanup
across timeout/submission/cancellation. Busy maps503, timeout408, malformed400.

Eleven focused parser tests passed, along with signedHTTP regressions. The route enables parser
offload only when a bound-history pool exists. On such a mixed server, ordinary Responses also
share parser capacity; two active signed generations can503ordinary intake beforemodeladmission.
Ordinary-only servers and embeddings retain current behavior. Explicit mixedserverHTTP test
proves no provider egress on busyordinary intake. Startup remains gated.

Local fullcheckpoint1056passed,2Linux-onlyskips,15Docker/Azurite deselected;88.78%coverage.
Ruff, formatting, mypy, diffwhitespace and257changed/plan relative links passed. Docker and
independent deepreview in progress; no liveprovider or production edits.

Independent runtime deep review cleared parseroffload with noCritical/Major findings. Strengthened
mixedserver test uses an unsigned backend/ordinary pool and blockedstartforwarding asserts upstream
response closed before backend shutdown.28HTTP tests passed. Docker build/health passed.

Updated Linux512MiB/2CPU8×100 aggregate replay:69successful/731preadmission503,zero postdispatch
failures,34,664,448incrementalRSSbytes; snapshotencoding1.81ms,workerrawparse28.22ms butloop67.25ms.
Parseroffload itself is verified; fullsignedresourcegate remainsfailed because workerPython scanning
still contendsforGIL. Separate JSONscanneroptimization plan requires independent review.
