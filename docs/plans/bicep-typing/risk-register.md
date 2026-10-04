# Bicep Typing Risk Register

## Risks

| ID | Risk | Impact | Mitigation | Status |
|---|---|---|---|---|
| R1 | Internal config migration changes GUID arguments | Duplicate assignment or conflict | Semantic comparison confirms original inputs/order | Mitigated |
| R2 | Optional object fields weaken mode guarantees | Invalid deployment inputs | Sealed required configs and literal compiler checks; runtime assertions retained | Mitigated |
| R3 | Typed object defaults alter root public API | CI/local overrides break | Public parameter definitions identical in compiled ARM | Mitigated |
| R4 | Module output adaptation loses app ordering | Storage access before grants | Compiled app dependencies unchanged | Mitigated |
| R5 | Refactor expands into unverified feature work | Baseline drift | Existing boundaries only; synthetic redeployment passed | Mitigated |

## Open Decisions
- Broader resource module extraction and the public discriminated deployment API remain Design target after this foundation.
