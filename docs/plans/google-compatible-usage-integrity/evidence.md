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
streamspassedprojects1/3/4. Nativepassedprojects2–5 (project1passedbeforecorrection).
Project1nonstreamverificationandprojects2/5streamsreturned503; noerrorbodyretryoccurred
because the originalanybytesbarrierwasoverlyconservative. All successfulcompatiblecalls
completedusage/settlement/cleanup withaggregateexcessincluded; originalfailuresunchanged.

Refineddiagnostic-onlystreambarrierpermitsretryafterHTTP503errorbodybutneverafterHTTP2xx
streambytes. Reviewclearedtwo remainingattemptsforonlyprojects2/5streamslots,pinningall
priorledgersandnonstreamprerequisites; newfocusedregression503->200SSEpasses.
