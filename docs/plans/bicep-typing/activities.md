# Bicep Typing Activities

## Step-By-Step Activities
1. Independently review this plan before implementing.
2. Save pre-change compiled ARM outside the workspace. Add common and state domain type files using exported literal aliases and sealed fixed objects.
3. Preserve public mode parameters as string declarations with their existing allowed decorators. Consume shared literal aliases through typed internal mode variables and use them in root expressions. Alias-typed parameters cannot retain allowed decorators. Document the minimum verified compiler as Bicep 0.47.16 (the currently installed version). Retain cross-field assertions.
4. Introduce sealed config objects for the existing registry/vault role modules and the new/existing storage modules. Preserve principal inputs and original GUID inputs/order. Group storage names together; group new-account location/tags with its configuration. Keep tags a genuinely open dictionary.
5. Return a typed, non-secret Table endpoint object from new storage. Adapt the root wiring without extracting additional resources or changing the public endpoint output.
6. Verify malformed config fields and invalid literals fail compilation using temporary fixtures. Compare compiled resources/properties/role identities before and after; account for nested parameter/interface changes without treating generator metadata as drift.
7. Build/lint, memory/new and memory/existing-storage and Table/new Azure validation, negative memory replicas, baseline what-if and smoke checks. Deploy the same synthetic memory baseline only after reviewing what-if; verify API behavior stays consistent. Do not raise replicas or change state backend.
8. Run repository full suite/coverage, Ruff, formatting, mypy and Docker build; perform independent deep review; run Sonar script if present. Update documentation/traceability and resolve relative links.

## Review Focus
- Typed contracts must be consumed, not merely exported unused abstractions.
- Public flat parameters remain compatible; do not introduce required public objects or change credential handling.
- Validate resource identity, endpoint guard behavior, new/existing scoping, and app dependency on the entire storage module.
- Avoid tuple-array mistakes and unrestricted objects except intentionally open tags.
