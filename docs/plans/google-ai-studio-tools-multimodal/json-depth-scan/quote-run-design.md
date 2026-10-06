# Finite JSON escaped-run scanner optimization

**Planned**,2026-10-06. Current signed quote-heavy feasible-max SDK probe succeeds in both
stream/nonstream and correctly settles, but observes174ms eventloopdelay/2.57sec request. The
existing deterministic scanner loops once per escapedquote and is repeated by canonical digest/
projection passes, including dispatch checks on mainloop. No runtime changes before independent
review. The separately reviewed quote resource harness records exact131072context/1.58MiBwire/
475488prospectivecarriers and successful framingheadroom; this is an accepted worstcase, not
an intentionally rejected oversized body.

Propose retain structural depth scan but skip JSON string contents using bounded-run regex:
`(?:\\[\s\S]|[^"\\]){1,256}` anchored match at current string position. Each alternative is
disjoint: backslash consumes exactly itself+onecharacter, ordinary consumes one nonquote/nonbackslash.
Quantifier bounded256 caps regexbacktracking state/allocations percall; no unbounded complete-string
repetition. Stop at unescapedquote, unmatched finalbackslash or EOF; strictjson.loads still owns
escape/control/unclosed validation. At mostlinearinputwork, boundedpercallstate and at most
input/256calls for uniform escapedruns; no copiedprefix or quoteparity rescans. A constant
structuralregex remains outside strings; braces/brackets inside strings skipped and original
MAXdepth/bytes/nodes/duplicate/nonfinite semantics preserved. Unicode/truncatedescape follow
strictdecoder; no provider schema regex feature is added.

Prototype1.225MiB/612783quotedcharacters scans12.42ms onlocal3.14 with2404boundedcalls; this is
prototype evidence only and needs memory/loop/adversarial measurements. Compare to current
scanner across ordinarystrings, alternatingescape/backslash/Unicode/control/end-of-string,
unterminatedstrings and structuralinside cases. Include exactdepth32/33 and duplicate/nonfinite/
nodecap regressions; differential accepted/rejected fixtures against currentdepthguard+strictJSON.

Independent review must establish no regexbacktracking blowup or semantic change. Run isolated
Linux2MiBplain/quotes/backslashes/malformed/Unicode measurement; constrain scanmemory/wall and
fullSDKsigned8×100RSS128MiB/maxloop50ms after change. Retain failed174ms/current runs. Focused/full
>=80%, Ruff/format/mypy/Docker/deepreview/docs required. Do not raise payload/capacity/timeouts or
remove strict canonical parsing merely to make a gatepass. If finite-run fails, investigate
reviewed perstage canonical-byte reuse/encoding-only internal ownedJSON or isolatedprocess work
separately. Startup/live/production gate unchanged.

Independent review condition: do not replace fast ordinary-string find with finite-run scanning
for every character; prototype2MiBplain55.39ms regresses baseline. Hybrid: inside string, first
use existing str.find+disjointbackslashparity; if quote is unescaped finish; if escaped, advance
past that quote then repeatedly anchored finite-run-match while nextcharacter is backslash.
When the nextcharacter is ordinary, resume str.find from that advanced position. This skips
uniform escapedquote/backslashruns256atoms/call, retains fast longplainruns, and never repeats
str.find toward the same distantescapedquote from successivechunks. If match fails at a lone
terminalbackslash, setscanpositionEOF and let strictdecoderreject. No semantic changes to
originalinput; percharacterprogress or finitechunkprogress ensureslinearwork. Reviewer81,623
valid/escaped/exactdepth cases agreed for boundedrun approach; hybrid needs own differential
and worstplain/oddbackslash/quote/Unicode verification before acceptance.
