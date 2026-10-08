# Historical verification records

The measurement JSONs and implementation-amendment designs in this plan are retained
as historical evidence for the linked child workstreams. They include failed,
preliminary, platform-specific, contended-host and successful synthetic experiments.
Keeping a file in version control does not establish that its workload passed, that
its profile was valid, or that it measured the current code.

Read each artifact with the corresponding workstream's `evidence.md`, which records
scope, limitations, corrections and superseding experiments. In particular:

- `jpeg-input/measurements/` and `native-pdf/measurements/` preserve parser and
  full-path experiments, including preliminary and rejected workloads.
- `audio-input/measurements/`, `video-input/measurements/`,
  `generated-image/measurements/` and `generated-audio/measurements-*.json` preserve
  finite media experiments. `generated-audio/fixture-bookkeeping-local.json` is a
  synthetic bookkeeping diagnostic, not resource or mixed-admission proof.
- `signed-continuation/measurements/` and `signed-continuation/quote-*.json` preserve
  successive resource experiments, including known failures and invalid historical
  fixtures. No early experiment supersedes later resource-gate failures.
- `signed-continuation/process-restart-local.json` and
  `signed-continuation/process-restart-linux.json` record synthetic fresh-process
  replay, not live inference or a production restart.
- The pending/approved design wording in historical amendment documents describes
  their original planning checkpoint. Current implementation status belongs to the
  workstream evidence and parent completion audit.

Runtime ledger lock files are transient synchronization artifacts and are ignored.
Redacted ledger JSONs remain audit evidence. Production deployment and exact-model
live validation are separate gates; none is cleared merely by archiving these files.
