# Foundry three-model inputs

Verified deployment metadata: gpt-6.1-terra (OpenAI, version 2026-10-26) and MAI-Image-2.6 (Microsoft, version 2026-07-31) succeed in both configured Foundry accounts. claude-sonnet-5-5 (Anthropic, version 2) succeeds in openclaw; expose logical claude-sonnet-5.5 as requested. The accounting release is deployed and committed as 3c9623e. User requests registering all three models in production; MAI through Responses image output.

Required references: canonical API/config/routing/credit/operations docs, existing Anthropic and generated-image pipeline/tests, Microsoft MAI API documentation and official Anthropic Foundry SDK. Deployment endpoint/auth metadata must be verified before promotion. Pricing requires verified USD meters or explicitly approved operator local estimates; the user has approved Sonnet 4/M input and 10/M output, and MAI USD 1 per bounded image request. Unrelated responses-request-limit plan remains untouched.
