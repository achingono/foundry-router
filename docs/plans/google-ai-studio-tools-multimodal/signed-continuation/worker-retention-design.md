# Signed worker exception lifetime

**Planned**,2026-10-06; independent review required. Current signed boundedwork helper awaits a
shieldedasyncio Task; failedtasktracebacks can keep its coroutine/runclosure/work/body alive until
cyclicGC. A syntheticweakref probe withGCdisabled found payload retained after completedfailure
andleaseclose. GeneratedPNGworker already has a reviewedanalogous task/closure detachmentfix.
This is a concrete lifetime issue, not proof itaccountsforallRSS orclientlatency.

Propose task-independentfinally detaches only coroutine-localreferences `task`, `work`, and
`before_submit` after completion/timeout/cancellation; also inspect runclosure's capturedwork and
consume callbackreferences to avoid leaving self-referential tracebackcycles. Must not break
shieldedworker ownership or slotrelease: timedout/cancelledjob retains itsrunclosure/work until
actualthreadcompletion, cleanupcallbackconsumeexception andcapacityfinish releaseonce unchanged.
Do not clear sharedclosurevariable `work` while thread isrunning (would invalidate execution).
Instead make runclosure capture separate defaultargument/local ownedfunction and delete caller
locals; threadfunctionfinally clears its localfunction after execution before task traceback
publication. Keep exactdeadline andboundedqueue semantics. Exceptions remain actionable safe
outererrors; no tracebackcontents/logs/payloads output.

Beforeimplementationreview exactreferencegraph and negativecontrol. Add meaningfulweakref
regressionGCdisabled for successfuljob, completedfailure, delayedsubmission/timeout/cancel with
ownedpayload: failure dropsimmediately aftercompletion withoutgc, activeworkerpayload retained
untilfinish, slotsneverreleaseearly, no swallowingworkerexception. Compareold helpernegative
control retainingpayload. Preserve testsboundedwork cancellation/deadline/doublecleanup and
signedactualHTTPreserve/drain. Full>=80%,Ruff/mypy/Docker/deepreview/docs; rerunfaithfulpreencoded
andoriginalSDKmaximumhistoryresources separately withoutconcurrentbenchmarkcontainers. No
capacity/limits/schema/auth/production changes, noresourcepassclaimfromweakrefproof alone.

IndependentreviewreproducedcompletedfailureGCretention and testedminimalreference-detachment
prototype: run(owned_work=work) capturesfunctioninitsdefault; runfinallydelowned_work; after
addcallbackdelrun callerlocal; outerawaitfinallydeltask/work/before_submit. Activejobusesdefault
so clearingcallerworkcelldoesnotinvalidateexecution. OriginalfailurepayloadretainsTrue, prototype
False; successesdropinboth. InitializeoptionalTask/runlocalsforprecreationfailurecleanup; preserve
consume/release_onceclosuresemantics. Finalpreimplementationclearance requiresactivecancel/
delayedsubmissiontests; no helperedityet.
