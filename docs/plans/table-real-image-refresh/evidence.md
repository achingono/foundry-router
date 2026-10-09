# Image refresh Evidence

Read-only audit confirmed prepared image b5af3588 predates reviewed forwarding change
b51c18d. Current Table plan requires reviewed current source. This was the pre-refresh
baseline; completed preparation and remaining approval gate are recorded below.

Independent reviewer cleared the platform-manifest verification/private-only mutation
contract with no Critical or Major findings. Approval must cover the refreshed digest.

Current runtime OCI archive built locally; linux/amd64 manifest and every config/layer
blob SHA256 verified. Private parameters changed only image; private inputs changed only
matching configuration fingerprint, with full-tree comparisons. Archive image loaded and
network-disabled runtime/Table imports passed (initial smoke used an incorrect class name;
corrected to the existing AzureTableEntityClient). Bicep compilation passed with existing
experimental assertion/CPU schema warnings. ARM validation returned Succeeded. All 33
existing Table binding/verifier checks passed. No runtime source change in this phase.

First read-only what-if exceeded the helper15second metadata deadline and was terminated;
no scope acceptance claimed from that attempt. The finite60second read-only check returned
Succeeded: exactly one app, two tables and two table-scoped role grants are Create;14 other
resources are Ignore and no other changes. See [safe scope](what-if.json), [validation](validation.json)
and [image digest](image.json). Pending image is
`registry.example.test/foundry-router@sha256:d8f68e5c638510a38ad30c3cadb80d96bd97ae1936a46c75083ac1b7d59fd438`.
No push, deployment,
inference, restart or production changes.

Independent final review found no Critical or Major issues in the safe artifacts. The stale
pre-refresh status sentence was corrected. Updated relative links and diff whitespace pass.

Operator approved the current isolated image push/deployment on2026-10-09. Registry push
completed and returned the exact approved manifest digest; see
[push result](../table-real-inference/push-result.json). The original `pushed:false` image
artifact records preparation-time state, not the later execution. Deployment is underway.
