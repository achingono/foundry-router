# Image-format exit criteria

- [x] Independent design review before runtime edits.
- [x] JPEG/WebP independently opt-in; defaults remain PNG only.
- [x] Container/type/pixels/bytes/aggregate/deadline checks before native decode and egress.
- [x] Corruption/truncation/bombs/metadata/animation cases and combined tools/schema tests pass.
- [x] Concurrent parser/mapping/encoding measurements recorded; limits retained.
- [x] Focused/full >=80% coverage, Ruff/types, Docker smoke and deep review pass.
- [x] Canonical docs/traceability/links/status updated.
- [ ] Exact-model live tests (separate gate; no inference authorization implied).
