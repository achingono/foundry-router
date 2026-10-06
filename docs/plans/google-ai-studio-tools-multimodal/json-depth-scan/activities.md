# Bounded structural JSON depth scanner

**Planned**, independent review required. Aggregate signed replay remains67.25ms maxloop despite
raw parseoffload; purePython percharacter depthscan touches every ciphertextbyte and competes
for GIL. Preserve load_bounded_json strict duplicate/nonfinite/depth/node/byte semantics.

The initial complete-string regex proposal was rejected before implementation: repeated regex
atoms allocated hundreds of MiB and held the GIL on2MiB fixtures. Use deterministic scanning:
constant single-character structuralregex searches for quote/brace/bracket outside strings;
inside, str.find locates the next quote. Count immediately preceding backslashes using length
difference of disjoint segment and segment.rstrip(backslash), then parity identifies an escaped
quote. Advance beyond every quote. Sliced segments are disjoint with total length<=inputcharacters; rstrip may add another linear copy and Unicode storage can require4bytes/codepoint;
no repeated-prefix scan or backtracking repetition. Unterminated strings stop structural scan
then strict json.loads rejects. Strings containing delimiters preserve exact depth.

Prototype macOS2MiB plain0.18ms,escapedslashes5.01ms,unclosed0.04ms;600kescapedquotes51.05ms.
Worstmanyquotes remains bounded work and requires worker/loop measurements; no passingmaxclaim.

Tests escapedquotes/backslashes/unicode/controlchars, structuralcharacters inside strings,
exactdepth/exceededdepth, malformedstrings, duplicate/nonfinite/nodecap remain; maximal2MiB
strings includingmanybackslashes benchmark and compare prioracceptedsemantic fixtures. Fullquality,
Docker/deepreview and Linuxaggregate measurement before completionclaim. No schema regexsupport
or network behavior introduced; no JSONcontentlogged.
