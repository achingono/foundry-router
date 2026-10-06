# Image-format inputs

- [Parent contract](../capability-contract.md) and [implemented foundation](../implementation/contract.md).
- [Image understanding](https://ai.google.dev/gemini-api/docs/image-understanding), fetched 2026-10-05,
  documents image/jpeg, image/png, image/webp and <=384 dimensions small-image token tier.
- Existing Pillow dependency, bounded PNG/helper tests, intake and billable failure lifecycle.
- Tiny deterministic images generated locally; no live model IDs inferred from format documentation.
- JPEG structure: [ITU T.81](https://www.w3.org/Graphics/JPEG/itu-t81.pdf).
- WebP structure: [RIFF container](https://developers.google.com/speed/webp/docs/riff_container).

## Input validation

- [x] Existing owning code/tests inspected.
- [x] Independent parser design review completed before runtime edits.
- [ ] Exact-model live inputs supplied (separate operator gate).
