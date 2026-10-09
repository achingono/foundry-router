# Google AI Studio capacity inventory evidence

**Partially implemented**, 2026-10-08. Five historical catalogs, 305 historical rows plus five newly discovered rows (310 total), 13 documented free-tier text model IDs, dated native outcomes and unknown provider quota fields inventoried. Actual project IDs, current tiers and shared quota-bucket identities remain uncaptured.

## Review

A separate agent session reviewed and cleared the plan before inventory creation, with mandatory handling of the repeated pilot as unclassified and ledger totals as retained reservations. Live amendment reviewed and cleared under the then-existing caps. The execution observer was started before its code review completed; review caught `overrun` versus `budget_overrun` return mapping. Execution was stopped, mapping corrected, offline success/failure interface checks passed, and remaining projects resumed. Initial attempts lack provider status and cannot be attributed conclusively to the observer mismatch; they remain ambiguous. No success was claimed from them.

## Local verification

310 unique project/model union rows; catalogs and manifest inspected. Historical counts 22 passes/17 failures plus one unclassified observation verified. Unknown provider fields and measured values checked against their exact source violations. Relative links in the new plan, documentation hub and operations hub passed. Cumulative merge checked: project-1 baseline 15 requests/12,928 reserved tokens; other projects 10/7,488 each. All stored entries counted conservatively, discovery once; earlier unledgered diagnostics prevent exhaustive spend claims. Numeric-only quota sanitization and corrected success/failure return interface checks passed. No runtime code changed; full pytest, coverage, lint/type checks, Docker and SonarQube are not applicable to this documentation-only change.

## Live authorization and scope

User explicitly authorized use of the existing Key Vault secret for live rate/limit measurement, then authorized as much available/needed budget as required, preserving zero paid spend. The initial finite series stayed within prior recorded caps. Keys fetched only into memory using the repository helper; no secret values or provider content persisted. Sandboxed fetch failed before dispatch; approved escalated execution fetched credentials. Provider root HEAD and Python GET reached HTTP 404 (expected root response), establishing basic network reachability only.

Detailed outcomes and limitations are linked from the inventory.

## Live findings

Five refreshed catalogs: 50 models each, HTTP 200. Survey: 65 attempts, 41 completed. Working-model ramps: 250 attempts, 211 completed, 22 RPM 429s and 17 other failures. Separate 2.5 Flash-Lite ramp: 28 attempts, 23 completed, two RPM 429s and three 404s. Large-input stages: 12 initial probes (seven HTTP 200, one useful completion), seven named input-TPM rejections, then 17 final input-TPM diagnostics. Paced daily stage: 297 attempts, 273 completed, 19 named daily 429s and five availability failures. Final five missing-daily probes all completed; those RPD fields remain unknown.

Provider-confirmed inventory: 24 RPM values, 24 input-TPM values (250,000), 19 RPD values (20). Five of the verified RPM buckets still lack daily metadata. Other catalog models retain unknown quota fields where inaccessible, unstable, not documented free-tier or untested. Actual project IDs/current account tier and cross-alias shared limits remain uncaptured. No inference content or raw error messages saved. The one interrupted router attempt has a durable debit but no persisted outcome; retained as unknown.

Separate final one-shot quota diagnostics intentionally followed daily exhaustion to seek missing TPM dimensions, as reviewed. They are not ordinary inference retries; all repeated ramps stopped at first failure and no quota bypass was attempted. Large prompt token values were estimates; source usage captures actuals where available. Independent contextual review found one Major documentation claim (operations hub incorrectly said TPM/RPD were still pending); corrected. Lead dates, current catalog union completeness, workload scope and capture timestamps were corrected as review suggestions. The separate review session verified the corrected catalog union and response-completion timestamps; final contextual review cleared with no open Critical/Major findings. Authoritative coverage of every catalog quota remains an open gate; measurement results are complete for the reviewed finite stages.

## Operator screenshot import, 2026-10-09

All five [screenshots](quotas.md) inspected visually, including project IDs in address bars.
Sixty-five visible rows transcribed with SHA-256 source hashes; quota denominators used,
not 28-day peak usage numerators. All 310 inventory project IDs populated; 44 unambiguous
model matches receive separate UI columns. Both selected exact models have displayed limits
on all projects. Historical provider measurements/bucket IDs remain unchanged.

UI TPM dimension, shared groups and ambiguous display-to-API mappings remain unknown.
Capture time is not visible; recorded date is not asserted as the capture timestamp.
This documentation import sends no traffic, fetches no credentials and renews no budget.

Independent visual/transcription review cleared with no Critical/Major findings. CSV uniqueness,
65 source-hash matches, all five project IDs, ten selected-model limits and relative links
passed. Comparison against the committed inventory confirmed every historical field retained
except the newly supplied project IDs; UI limits occupy new columns. Final diff check passed.
Runtime tests/build are not applicable to this documentation-only import.

Operator clarified that all five projects belong to separate accounts. Planning now states
independent project quota pools explicitly; same-project/model counters across router
replicas are separate from account independence. Alias mapping is only a conditional gate
when aliases/variants are selected. No quota limits or runtime settings changed.
