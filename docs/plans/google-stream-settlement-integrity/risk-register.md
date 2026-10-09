# Stream settlement Risks

| Risk | Mitigation |
| --- | --- |
| Treating first valid event as completion | Require clean EOF/finish or complete signed prefetch |
| Losing original estimate during prefetch | Retain fallback before all ownership transfer awaits |
| Changing quota with cost policy | Keep valid input observation separate from precise cost |
| Reclassifying failed live result | Immutable evidence; local-only proof |
