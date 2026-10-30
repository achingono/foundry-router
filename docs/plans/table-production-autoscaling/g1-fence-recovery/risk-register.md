# G1 fence recovery Risk Register

## Status: Planned

## Risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| FR1 | Consumed outer apply mistaken for paid-slot consumption, or inverse | Unnecessary new funds or duplicate paid dispatch | Bind original ledger/history; four wholly unstarted slots only; exclusive original slot markers and parent lock, no old apply replay | Open |
| FR2 | Immediate ingress GET precedes propagation | Another stranded mutation | Genuine120second total status waits including nested reads, desired403/200 observation, bounded polling not mutation retries | Open |
| FR3 | Min0 scales away during review | Stale process binding or account drift silently accepted | Independently approved narrow warm-old-image branch, exact finances/settings, fresh recorded baseline before fence/drain | Open |
| FR4 | Writer shutdown metadata lags | Old/new simultaneous account spend | Count all inactive draining replicas; no active revision/workers before PATCH; bounded total absence observation | Open |
| FR5 | Marker/journal lost acknowledgement or concurrent recovery | Slot replay and understated liability | Common original/parent/recovery locks, exclusive fsynced consume-before-dispatch markers, preserve uncertain consumption, no second recovery replay | Open |
| FR6 | CLI adds empty values to secret references | Configuration drift after old writer stopped | Existing exact template-only REST proposal/hashes; preserve secretRef-only records; one PATCH/no repair retry | Open |
| FR7 | Cold-start or case drift adopted as new funds | Invalid financial continuity | Original two accounts unchanged; baseline→before→after equality, legacy counters0 explicitly historical baseline, no seed/reset/refund | Open |
| FR8 | Completed terminal without EOF or no-op restart accepted | False G1 production prerequisite | Bounded terminal+usage+EOF; changed actual container/process and persisted finances; strict reviewed result-chain schema | Open |
| FR9 | Cleanup or production resumed implicitly | Exposure or concurrent writer ownership | Staged DENY/min1 retained; separate ingress/min0 cleanup packet; terminate and notify writer release | Open |

## Open Decisions

- Exact new private recovery directory/identity, runner/test hashes and append-only journal/link names are assigned by the coordinator and bound before approval; no guessed hash or runnable path is supplied by this planner.
- Cold-start is conditional on actual min0 state at execution. Approval must cover rebaseline explicitly; unchanged finances/settings are mandatory in either branch.
- Production G1 prerequisite must validate the linked recovery's actual four-pass/restart schema, not merely presence of a new results file. Agree reader/result-chain compatibility during exact review; no fake original success artifact.
- Retained original ingress/min0 restoration remains outside this recovery. Later cleanup must use captured exact inputs and fresh actual state, not old-image activation.
