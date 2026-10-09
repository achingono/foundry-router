# Google usage evidence

Same-wire prompt7/completion2/total71 confirmed no reasoning metadata; signaturewrapperstandard.
Originalstagehaltedand immutable; newusageprobe1physical, total3consumed.

## Local correction

Google-owned normalization conserves valid aggregate total through nonstream translation,
usage extraction and stream snapshots. Missing completion remains unknown; total below
prompt/split rejects; later partial snapshots clear known output, decreasing complete
snapshots reject. Generic providers and embeddings retain their behavior. Unattributed
excess is conservatively accounted as output, with no reasoning claim.

Focused adapter/compatibility tests passed59; actual snapshot-order tests passed11;
remaining-runner/pinned-budget tests passed. Independent contextual implementation and
runner reviews cleared Critical/Major findings. Ruff/format and strict mypy pass. Full
suite: 2,088 passed, 3 skipped, 19 deselected, coverage89.86%. Final amd64 Docker build, network-disabled app import and aggregate-usage smoke passed; scanner script absent.

Remaining runner amendment independently reviewed: unique project-1 corrected nonstream
verification consumes its last physical slot allowance, with no retry; original failed results
remain immutable. Other unused cases retain bounded retries; combined upper bound43
physical attempts under45. Production configuration/image remains unchanged.

## First corrected all-project assessment

[Remaining ledger](../google-38-responses-diagnostics/remaining-ledger.json) contains14
physicalattempts, allsingle-attemptcases. Corrected nonstream Responses passedprojects2–5;
streamspassedprojects1/3/4. Nativepassedprojects2–5 (project 1passedbeforecorrection).
Project 1nonstreamverificationandprojects 2/5streamsreturned503; noerrorbodyretryoccurred
because the originalanybytesbarrierwasoverlyconservative. All successfulcompatiblecalls
completedusage/settlement/cleanup withaggregateexcessincluded; originalfailuresunchanged.

Refineddiagnostic-onlystreambarrierpermitsretryafterHTTP503errorbodybutneverafterHTTP2xx
streambytes. Reviewclearedtwo remainingattemptsforonlyprojects 2/5streamslots,pinningall
priorledgersandnonstreamprerequisites; newfocusedregression503->200SSEpasses.

## Final bounded retry evidence

[Retry completion](../google-38-responses-diagnostics/stream-retry-ledger.json) used the
remaining two stream attempts on projects 2 and 5. Project 2 returned 503 twice, exhausting
three total attempts. Project 5 returned 503 then 200, passing completion, aggregate usage,
synthetic settlement and cleanup on its third total attempt. No successful stream was retried.

[Summary](../google-38-responses-diagnostics/summary.json): native passed 5/5 projects;
corrected nonstream Responses passed 4/5 (project 1 verification returned 503); streaming
passed 3/5 initially and 4/5 eventually. All successful compatible cases cleared reservations
and matched synthetic settlement. Historical accounting failures remain unchanged. No new
400 parameter rejections were observed. This small sample is not a reliability estimate.

Combined 21 physical attempts reserve 22,848 tokens under the 45-attempt/48,960-token bounds,
with zero paid spend. Exhausted slots cannot use remaining global headroom. Final full suite:
2,089 passed, 3 skipped, 19 deselected; coverage 89.86%. Ruff, formatting, mypy and amd64
build/runtime smoke passed. The final retry change affects only the verifier.

Production remains memory/one with unchanged image/configuration. Calls used the actual
Responses route locally against Google, not a deployed production endpoint. Production 3.8
enablement requires a reviewed image/configuration rollout and deployed acceptance. Retain
operation-specific eligibility limits for project 1 nonstream and project 2 streaming.
