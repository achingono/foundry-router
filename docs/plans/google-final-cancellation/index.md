# Final Google stateless cancellation acceptance

**Implemented locally**,2026-10-09UTC; final live acceptance pending. Latest three recorded normal streams produced actual public
completed events, matching independently observed input/output counts/debits, early text
before provider EOF and natural cleanup, but failed an additional verifier-only inertstop
predicate. Those failed outcomes remain immutable; their raw stop shapes are unknown.
One cumulative project2 request slot remains; no other project can be called.

## Correct verification boundary

The actual Google stateless stream decoder owns provider choice/delta/signature/finish
validation. Duplicating a stricter inertstop predicate in an independent usage observer
can falsely reject valid final output/signature envelopes accepted by that decoder.
Keep the bounded independent usage observer for maxima, token caps, nonfinite/invalid/
nonmonotonic accounting and early delivery; do not reuse provider outputs for evidence.
For this new verifier contract, a normal completed public response plus fully matched
independently observed integer usage/maxima, provider [DONE] and EOF, no invalid/overrun
and exact local debit proves the local completion/settlement path. Do not require a
separate inertstop schema or infer missing protocol state from unknown provider fields.
Use the same existing GoogleStreamDecoder in a verifier-owned mirror to validate already
received chunks, with exact request context/model and bounded storage; the mirror never
translates new provider calls. Final mirror.finish must succeed and no response.failed/
incomplete terminal emitted. Independent observer still must retain all known maxima before
mirror validation can fail. This adds at most one additional bounded text assembly; document
its resource scope. Discard mirror feed outputs immediately. Clear/reset mirror state at close without calling
finish to fabricate termination; mirror.finish is called only after observed upstream EOF.
No outputs/signatures persisted.
Public actual route completion remains required for normal cases. Mirror evidence is not
production compatibility proof or a replacement for the actual route.

Do not edit old decoder/runner defaults or old result files to retroactively clear failures.
Add optional verifier injection for this new contract only. Safe evidence records mirror
terminalvalid bool, independently complete_usage bool, decoded_done bool and upstreamEOF.
Counts/flags/timing only; unknown provider messages/states never saved.

## One remaining cancellation request

After separate plan/implementation review and local quality, run exactly one new project2
cancellation case on gemini-3.5-flash-lite compatible Responses, frozen prompt `List the
integers from 1 to 200.`, provider-default thinking, stream=true,maxoutput1024, inputcap64,
reserved1088, paidspend0 under existing operator authorization. Capture the current full
ledger as new immutable baseline. Refuse any changed prefix/missing baseline/consumed new
ID, globaloverrun, unexpected entry or ambiguous started/progress/result. No retries/reset.
Use immutable latestthree normal result artifacts as an EXPLICIT prerequisite, pinned by
SHA256 of the exact recorded result bytes and exact project/model/case bindings validated
against current ledger actual counts: require
provider/public200,actual publiccompleted,earlytext,independent consistent counts/max<=1088,
observeddebit=count/1000,naturalcleanup,nobudgetoverrun or invalidusage. Preserve their
failed strictterminalstatus and scope: this prerequisite does not retroactively reclassify
those failed gates. It establishes only the already observed successful local route facts.
Do not require another normal provider call or consume a slot from exhausted projects.

Use real owned loopback listener/client and immediate usage observer. Disconnect on first
meaningful publictext BEFOREupstreamEOF/[DONE] and before mirror terminal completion. Require
oneproviderdispatch,upstreamclosure,naturalreservationrelease,no retries/failover,conservative
local fallbackdebit if complete usage unavailable. Independent partialcounts remain lower
bounds, not provider finalbilledcost; fullbudgetreservation never refunded. No forcedreaper
can clear success. Same25srequest/<30stotal+boundedcleanup, durableprogressbeforeawait,
strictnewfixedschema and consumedinvocation lock. Any ambiguity/failure retains failed
result or startedmarker and closes the gate; do not repeat.

## Verification

Test actual signature-bearing finaldelta and finaltext+stop support through mirror and
actualroute, malformed/unknownstate rejects, independent overrun retained before mirror
failure, missingdone/truncated mirrors rejected, matching normal usage/debit. Test latest
prerequisite artifact corruption/partialproof, exhausted/changed historicalledger, onecase
replay/crash/globalhalt, natural earlydisconnect/unknownusagefallback. Fullquality>=80%,
Ruffformat/lint,mypy,contextualreview; verifier-only noDockerrebuild. Commit phases. No
production/deployment/cost queries or Googlequota probes. Cancellation success clears only
project2/exactmodel/localloopbackroute; capacity/nonzerothought/deployedadmission/metrics/Table
production and scaleout gates remain unmet.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
