# Canonical encoding validation without redundant JSON decoding

**Planned**,2026-10-06; independent review required before runtime changes. Current attribution
shows routercanonical_bytes called129738times in59dispatches for125itemhistory, with worker
build/check maxima285/150ms and digest57ms; SDKencoding/postfixturechecks separately affect
mainthread. Canonicalencoding reparses every locallyencodedJSON using the quote scanner even
though json.dumps generated syntactically valid JSON. This is evidence-driven duplication,
not justification to relax bounds or signature/history/configuration binding.

Investigate a narrowly scoped equivalent validation: canonical_wire_bytes already recursively
requires stringkeys, depth<=32,nodes<=16384, finite JSONencoding, validUTF8, wirebytes<=cap and
strict allow_nanFalse. For values supported by json.dumps, the encoded document is syntactically
valid and duplicatefree if allkeysarestrings; locallyencodedJSON does not require escapedquote
scanning to establish depth. Existing tuple input becomesJSONarray; node/depth validation must
cover both list/tuple exactly. Reject unsupportedbytes/sets/customobjects, nonfinite, badUnicode,
nonstringkeys andcycles before returning. Preserve sortkeys/ensure_asciiFalse/separators and
byte-identical output/digests/tokens. External rawJSON decoding still uses unchanged strict
load_bounded_json for duplicate/nonfinite/depth/node/byte/malformed validation.

Before choosing implementation, independentreview must prove canonical_wire_bytes recursive
bounds equivalent to current canonical_bytes+decoder across supportedPythonvalue forms,
including int magnitude, bool,floatnegativezero,stringUnicode/unpairedsurrogates, intsubclasses,
container aliases/tuples/cycles/depth/nodes, dictsubclasses/keys. If equivalence holds, remove
only redundant locallyproducedJSONparse from canonical_bytes and clarify ownership docstrings;
otherwise introduce encoding-only helper solely at reviewed immutable validatedsnapshot paths
and keep generalcanonical contract. Do not cache caller-ownedmutableobjects or skip digests on
selection/dispatch; replay/state/history scope checks remain exact and fresh.

Differential test against preserved oldencoder+load_bounded_json oracle, exhaustive/synthetic
seeded values and exactdepth/node/bytes boundaries, identical rejection/outcomes/digestwire;
no new network or dependencies. Run focussed signed/state/intake/tool/media/SDK andfull>=80%,
Ruff/format/mypy/Docker/deepreview/docs. Re-run originalSDK andfaithfulpreencoded125history8x100
profiles with current-sourceSHA, same128MiB/50ms/60sec bounds. Retain earlierfailedartifacts;
a lowerduplicatevalidationcost alone doesnotprove all maxima or combinedmedia/resourcecompletion.

Independent review disproved unrestricted equivalence: dictsubclass can overrideitems to emit
samekeytwice; canonical_wire_bytes acceptsduplicatelocallyencodedJSON whileexistingcanonical_bytes
rejects it. Preserve generalparsefallback. Amended proposal: extend existing recursive_string_keys
walk with exactbuiltin-tree eligibility boolean, returnedfromsamebounds traversal (no secondwalk).
Eligiblevalues exactNone/bool/int/float/str/dict/list/tuple, exactstrkeys; recurse onlyexisting
list/tuple/dictvalue traversal while retainingexistingdepth/node checks. Any subclass anywhere
marksfastpathineligible and usesoriginalcanonicalparse afterjson.dumps. Do not reject harmless
subclasses previouslyaccepted. ExactbuiltinJSONencoding cannotproduceduplicatekeys; tuplearray
mapping preservesdepth/nodecounts. canonical_wire_bytes publicshape unchanged; internalhelper
returns(encoded,eligibility) andcanonical_bytes conditionallyparses onlyfallbackcases. General
badkey/surrogate/NaN/cycle/unsupported-type/largeint behaviors retained. Addduplicateemittingdict
subclassregressionplusacceptedharmlessdict/list/string/intsubclass cases; differentialoracle
mustprovebothfast/fallbackpaths. Stillrequiresexplicitindependentreviewbeforecodeedit.
