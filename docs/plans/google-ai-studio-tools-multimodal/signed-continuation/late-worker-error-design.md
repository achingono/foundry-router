# Late signed worker error handoff

**Planned**,2026-10-06; separate independentreview before code. Requiredretentiontests reproduced
Python3.14asyncio.shield latefailedinnerTask loop exceptionhandler event containingrawValueError
message aftertimeout/cancel, even Taskexceptionconsume callback. That eventretains payload and
canlog sensitiveparser/upstreamcontext. Existingruntime hasthisbehavior; no broadexceptionlog
suppression orglobalhandler changes proposed. Retentionfixcurrentlycompletedfailurepasses,
latefailuregatefailscapturedloophandler; keepfailureexplicit.

Propose replace asyncio.shield at thishelperboundary with ownedplainasyncioFuture+Taskcallback
handoff. ThreadTaskcontinuesindependently; awaitingcaller cancellation/timeout cancels onlyplain
handoffFuture (no3.14shieldcallbacks). Existingconsume release_once remains. Separatehandoff
callback obtainscompletedTask result/exception exactlyonce; ifhandoffcancelled, retrieveexception
withoutpublishing/logging, retainingnormalexceptionpropagation ifcalleractive. IfTaskcancelled,
cancelhandoff; otherwise setresult/setexception onlyifnotdone. Do not wrapexceptions in generic
success orhide normalfailures. Callback owns FutureonlyuntilTaskcompletion, outerfinallydrops
callerTask/Future/work/before_submit/runreferences; futurecancel breaksabandonedresultchain.
NormalfailedresulttracebackmustnotcycleFuture→callback→Task→work; inspectreferencegraph and
weakrefGCdisabledtests. Beforetaskcreation/submissionerrors stillrelease capacity once; delayed
jobs/defaultownedworkretainpayload untilthreadfinish. No operation retry orfinance changes.

Test originalnegativecontrolrecordsrawmarker on3.14, newhelpercapturedloophandleremptyforlate
failure on3.14andLinux3.12; normalfailure ValueErrorpropagatesunchanged, cancellation/timeoutexact,
activecapacityneverearlyrelease, latepayload dropswithoutGC, successdrops, callbackdoubleclose
safe andprecreation/delayedexecutor gates. Focussed/full>=80%,static/Docker/deepreview/docs and
sequentialmaximumresource repeats. Separate redactionfixpublicstatusunchanged; nodisablelogging,
no service/network/config/prod writes; startup remainsgated.
