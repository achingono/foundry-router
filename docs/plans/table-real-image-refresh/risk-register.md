# Image refresh Risks

| Risk | Mitigation |
| --- | --- |
| Pinning config or attestation digest | Select platform manifest and hash OCI blob |
| Unrelated private configuration changes | Compare full original parameter tree except image |
| Treating pending approval as granted | No external writes; scope remains pending |
