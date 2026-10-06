# Evidence

**Partially implemented**, 2026-10-06. Finite raw BGR DIB AVI input uses standard input_file,
strict RIFF/header/frame/timing/padding checks and immutable per-candidate facts. Native mapping
injects fps1; price/inputTPM bounds require operator affirmations. No codecs or external I/O.
Independent review found no Critical/Major finding; a minimum-file-size error was corrected
from244 to236bytes with a successful smallest1×1fixture and actual padding-validation test.

62 parser/config tests and3 SDK/HTTP integration tests pass. Actual OpenAI2.8.1 create/stream,
ordered AVI/WAV native parts, full history, lower-cap candidates/three-project429failover are
synthetic provider fixtures. Four direct ASGI blocked-send tests now cover audio/video and
response-start/body stalls: close and known usage/credit/inputTPM settle once. This does not
establish real TCP disconnect or distributed exactly-once behavior.

Final video checkpoint:1179passed,2Linux-onlyskips,15Docker/Azurite deselections,
89.00%coverage; whole-tree Ruff/format/mypy pass. Minimum-size correction and extra integration/lifecycle tests are included. Docker build passes.

[Linux video workload](measurements/video-http-linux.json):8callers×100, two4frame64×64clips,
networkdisabled512MiB/2CPU, alternatingstream/nonstream,800successful responses; observed sampled
RSS growth10620928B,maxloop19.98ms,request33.33ms. Clips reach frame/dimension maxima, not
65536bytes/file. Benchmark image preceded minimum-size correction; maximum fixture unaffected.
Combined actual media/state/wire maxima remain pending.

Exact model raw AVI codec acceptance/pricing/inputTPM/live enablement remain unverified.
Catalog discovery does not prove them. Default-off; signed startup gate and production unchanged.
