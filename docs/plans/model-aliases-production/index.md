# Model Aliases Production Rollout

## Companion Documents
- [Inputs](inputs.md)
- [Activities](activities.md)
- [Outputs](outputs.md)
- [Exit Criteria](exit-criteria.md)
- [Risk Register](risk-register.md)
- [Evidence](evidence.md)

## Status
**Implemented** for deployment, live inference and synthetic actual-client approval validation; unfenced credit continuity and GitHub CI remain limitations. The user authorized production deployment, live inference and actual approval-client validation on 2026-10-05. This does not authorize weakening approval policy or claiming reviewer equivalence from HTTP success.

## Objective
Deploy the reviewed explicit model-alias implementation to the existing production app, configure both requested aliases to the existing gpt-6.1-sol pool, and verify bounded live inference and actual approval-client outcomes.

## Scope
Preserve the existing production resources, credentials, backend pools and memory/one topology. Build from a manifest-verified export after local quality/Azurite checks and remote Docker smoke. The user subsequently directed Bicep deployment from the supplied local production inputs. Do not push main merely to trigger its unrelated staging deployment. No Table cut-over, credential rotation, new permanent infrastructure or reviewer-policy overrides.

## Entry Criteria
The earlier implementation review findings are closed. Current Azure configuration, target readiness, rollback image/revision and required build/CI gates must be verified before production mutation.

## Roles
- Owner: Codex deployment session.
- Reviewer: Independent session required by repository AGENTS.md.
- Approver: User, through the explicit deployment request; command sandbox approvals remain enforced.
