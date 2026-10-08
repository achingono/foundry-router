# Canonical empty-container depth correction

**Planned**, 2026-10-06; independent review before correction.

The prior exact-builtin canonical optimization has a confirmed boundary discrepancy. The eager
walk uses zero-based value depth and rejects values deeper than 32; the original JSON scanner
counts containers from one and rejects nesting above 32. A chain of 33 empty lists (or empty
objects) ends at value depth 32 and is accepted by the fast path, but the original scanner
rejects it. Scalar leaves at that depth are allowed. Existing depth tests used only scalar leaves
and missed the empty-container case. The signed startup gate remains closed; no live use.

Keep canonical wire encoding's old acceptance unchanged. Extend the eager walk to return two
facts: exact builtin eligibility and encoded-container-depth eligibility. Every dict/list/tuple
at value depth >=32 marks the latter false; scalar leaves at depth32 remain eligible. Propagate
both facts eagerly through all children. `canonical_bytes` skips parsing only if both hold;
otherwise retain the original bounded parser. `canonical_wire_bytes` still returns its original
wire without any new rejection. This avoids breaking that helper's deliberately looser contract
and retains subclass fallback validation. No change to limits, parser, hashing, caches or APIs.

Test list/tuple/dict and mixed nested empty containers at 31/32/33/34 levels, scalar leaves at
32, subclass fallback, node/byte/Unicode/finite bounds and canonical_wire_bytes original behavior.
Independent differential review, focused/full >=80%, static checks, Docker and signed/client
resource rechecks are required. Projection snapshot proposal remains unimplemented until this
correction and its own proof are reviewed. Document the earlier differential evidence's missing
empty-container boundary rather than claiming it covered all possible trees.
