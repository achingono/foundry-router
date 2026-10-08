# Decoder-owned structural string scanning

**Planned**, 2026-10-06; independent review before code.

Quote-heavy signed resource checks still fail. The external bounded JSON depth pre-scan manually
skips escaped string runs in Python before the original strict JSON decoder. A local synthetic
probe on a 1.09 MiB quote string takes about 12 ms for the existing bounded decoder, whereas the
standard-library decoder's `json.decoder.scanstring(text, start_after_quote, True)` takes about
1.4 ms for the string portion. This is microbenchmark evidence only, not a resource clearance.

Propose replace only the pre-scan's manual quote/backslash skip with `scanstring` using strict
mode. It returns an owned decoded string and end position; discard the decoded string immediately.
Retain `_STRUCTURAL_JSON` search and original container depth counter, exact input byte limit,
final `json.loads` with duplicate/nonfinite rejection, and eager node/value validation. Catch
its JSONDecodeError and map to the existing safe invalid-bounded-JSON ValueError. No parser
repairs, remote resolution, caches, increased depth/size limits or alternate accepted JSON.

Review requirements: `scanstring` strict mode must be equivalent to the final decoder's string
syntax/escaped quotes/backslashes/control/unicode behavior on Python 3.12 and 3.14. Decoded string
allocation is temporary and bounded by approximately four times the input bytes plus Python
string overhead (mixed ASCII/astral strings use four-byte code points); examine malformed/incomplete
strings and surrogate escapes, guarantee forward progress and no nested parser recursion. This
uses the standard-library decoder primitive, not a custom permissive parser. If its API stability
or resource behavior is unsuitable, reject before implementation. Avoid retaining allocations
across structural searches.

Differential tests must cover quote/slash runs, malformed escape/control/unicode strings, exact
container depth with braces in strings, duplicate keys, nonfinite/huge numbers, byte/node bounds,
unicode and randomized valid/malformed text. Keep strict final decoder and exact errors safe.
Run original scanner oracle versus candidate, focused/full coverage, Linux3.12/local3.14,
static/Docker/deep review and original sequential unprofiled fullSDK/resource checks. Record both
failed and passing artifacts without relaxing 128 MiB RSS / 50 ms event-loop caps. Production
and signed/media startup gates remain separate and closed.

Independent review passed 39,539 valid/malformed differential cases. The allocation bound is
corrected to four times input bytes plus overhead; delete the temporary before final decoding.
Catch ValueError from the primitive as safe invalid bounded JSON, covering JSONDecodeError.
