# Signed continuation risks

| Risk | Control |
| --- | --- |
| Standard client drops extension | Pin actual SDK; test terminal items/snapshots/model_dump/full replay; unsupported clients disabled |
| Cross-caller/backend/history replay | Server HMAC scope, authenticated envelope, config/history/order binding and pinned candidate |
| Late signature leaves completed call unsafe | Delay completion until final envelope; incomplete terminal on missing/invalid state |
| Native SSE fragment identity ambiguous | Initial signed public stream uses fixed generateContent nonstream upstream; no inferred SSE Part ordinals |
| Signature placement differs by model | Preserve exact native Parts; operator explicit contract and separate live gate |
| Envelope size/work amplification |64KiB aggregate signature bytes/turn; token<=min128KiB/256KiB-divided-by-itemcount;512KiB all repeated input carrier bytes; incremental2MiB history hashing |
| Key/config rotation breaks conversation | Bounded overlapping decrypt keys; operator generation; document restart/drain/revocation |
| Reasoning underreservation | Separate bounded configured thinking budget included within total upstream output limit and price affirmation |
