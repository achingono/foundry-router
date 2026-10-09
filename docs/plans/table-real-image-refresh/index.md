# Refresh prepared Table inference image

**Planned**. The prepared isolated Table inference image predates subscription currency and
stream accounting corrections. The [Table test plan](../table-real-inference/index.md)
requires reviewed current source. Refresh preparation before the pending deployment approval.

Build the current committed runtime as linux/amd64 into a local OCI archive, preserving
the earlier prepared image evidence. Read the archive index to select the actual linux/amd64
manifest digest, never the image config digest or attestation manifest. Confirm archive blob
digest integrity, source revision and bounded archive metadata. No image push.

Update only image reference in existing gitignored Table parameters and recompute the
matching private configuration fingerprint; all tables, app names, grants, identities,
secret versions, ingress, model limits and budgets stay unchanged. Verify the private
contract using existing binding validators. Run network-disabled image import smoke,
Bicep compile and bounded read-only ARM validation/what-if. Keep identifiers/credential
values out of public output, retaining only safe digest/status/write-count evidence.

Have this plan independently reviewed before preparation mutation; review final changes
and document exact scope. Commit phase transitions. No provider calls, production changes,
push, deployment, restart or billing requests. Existing concrete approval is pending and
must cover the refreshed digest before external writes.

- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit criteria](exit-criteria.md)
- [Risks](risk-register.md)
- [Evidence](evidence.md)
