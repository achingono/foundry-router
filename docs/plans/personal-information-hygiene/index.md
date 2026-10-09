# Personal information repository hygiene

## Status: Implemented

## Objective
Keep operator screenshots and their project-identifying derivatives local, remove them from Git tracking, and prevent their accidental reintroduction. Audit tracked files for account identifiers, personal contact details, private paths and credential patterns without recording their values.

## Scope
Ignore and untrack the five quota screenshots and `inventory.csv`, `quotas.csv`, `quotas.md` in the capacity inventory plan. Preserve these files on disk. Preserve original registry-account evidence under ignored `private/personal-information-hygiene/` and sanitize any real private account identifiers found in otherwise useful documentation/evidence; retain public examples, synthetic test values and public Azure role IDs. Add ignored `private/` and `screenshots/` locations for future operator captures. Update links to local-only artifacts to plain paths with an explicit local-only notice, preserving the recorded validation scope.

## Sequence
1. Inspect the cited commit, tracked text/binary files, ignore rules, canonical security/development docs and artifact consumers.
2. Obtain an independent session plan review before implementation.
3. Add ignore rules, remove the eight private artifacts from the index while preserving disk contents, and sanitize additional account identifiers.
4. Update documentation for local-only evidence and future capture handling.
5. Verify ignore rules, no tracked ignored files, no known private values in remaining tracked content, relative documentation links and diff whitespace. Run independent contextual review using the repository deep-review prompt. No runtime or infrastructure changes; runtime tests, coverage, Docker and type checks are not applicable to this documentation/index-only change. SonarQube script is absent.

## Boundaries
Gitignore does not remove earlier commits. History rewriting and remote force pushes are outside this change. Preserve local originals and do not copy private values into this plan or review output.

## Companion documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
