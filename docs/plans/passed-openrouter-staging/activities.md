# Passed-model staging acceptance plan

1. Accept only the two passing models from the new roster: `gpt-6-luna-or` (`openai/gpt-6-luna`) and `claude-haiku-5.5-or` (`anthropic/claude-haiku-5.5`). Their nonstream public/admin acceptance is historical, not a fresh health guarantee.
2. Independently review this scope. Validate retained results locally and check current staging revision/pool bindings read-only with bounded admin reads. No inference replay or new identity.
3. These two pools were historically deployed; confirm fresh readback; do not restart the memory app or rewrite secrets merely to deploy them again. Preserve existing unrelated pools,auth,global/group policy,image and ingress. DeepSeek,MiMo,Spark are excluded from the accepted new roster; they are not removed from runtime configuration by this decision.
4. Save a concrete two-pool local selection artifact and documentation for using the passed pools. This selection artifact is not a runtime allow-list or production configuration. Update hub,operations and traceability.
5. If readback is unavailable,report it accurately; existing historical passes remain historical. No claim of current availability from past results. No production qualification,stream qualification,topology pruning or new live spending. Configuration removal would need a drained/all-account seeded scoped rollout.

Documentation/selection-only change: no runtime tests,coverage,Docker or Sonar needed; local manifest/result validation,relative links,whitespace and independent scope review apply. Existing code verification remains in prior evidence.
