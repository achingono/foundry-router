# Register three existing Foundry models

Status: Implemented and deployed; live acceptance passed and public intake restored. See [production evidence](production-evidence.md). User requests gpt-6.1-terra, claude-sonnet-5.5 and MAI-Image-2.6 in the deployed router; user chose Responses image output for MAI.

## Implementation boundaries

Terra uses existing azure_foundry Responses backend unchanged, with exact verified pricing. Add provider azure_anthropic as a thin specialization of the existing nonstream text Anthropic adapter, route resource-root /anthropic/v1/messages and replace inbound auth with SDK-established server-owned x-api-key AND api-key plus server-owned anthropic-version. Reject streaming, tools, media and unsupported options before dispatch; expose logical Sonnet spelling separately from deployment claude-sonnet-5-5. Count Anthropic cache-inclusive inputs at a safe configured ceiling; no unverified cached discount or model-specific hardcode.

Add provider azure_mai with Responses-only, nonstream generation: string input prompt bounded to 64KiB, exact image_generation tool requesting PNG 1024x1024, no history/media/edits/web grounding/aspect overrides. Route resource-root /mai/v1/images/generations with api-key; physical model substitution, fixed width/height and one output. Pure adapter projects one canonical validated PNG into Responses image_generation_call, without fabricated text/tokens. Reuse existing request-owned Linux PNG worker and bounded delivery pipeline. Validate canonical base64, one-image envelope, bytes/pixels/digest bounds in the worker before exposing output. Reserve exactly one strictly positive operator image_output_per_image estimate; retain the fixed reservation cost through existing translated forwarding (image-output retain_full_cost). Missing token usage must never turn a billable generation into zero debit. Validate image-only pools and safe non-token pricing config; reject streaming/incompatible operations and mixed-provider capabilities at configuration/intake. Generalize only the provider-owned branches needed; existing Google image/audio and other provider behavior remain unchanged.

Use existing credit groups/credentials and verified resource endpoints; arbitrary pools remain supported. No deployment IDs/endpoints/prices are hardcoded in runtime source. No new public API or Azure model resources. Document initial nonstream capability limits. All 17 existing backends, 11 pools and aliases preserved; add five backends and three pools. The coordinator is the sole source writer; separate reviewer approves plan and reviews implementation/exact release, verifier measures gates. Source changes wait for plan approval. Live pricing and execution used exact reviewed packets and data; preserve memory state through the previously proven fenced drain and old-writer exclusion. Diagnostics should minimize repeated remote exec to avoid throttling; retry-after is respected and no inference replay after ambiguous receipts.

References: [inputs](inputs.md), [activities](activities.md), [outputs](outputs.md), [exit criteria](exit-criteria.md), [risks](risk-register.md), [evidence](evidence.md). Official contracts: [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image), [Anthropic Foundry SDK](https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/lib/foundry.py).

Preserve the existing Google generated-output startup gate. MAI uses the same
finite PNG inspector (<=1MiB RGB/RGBA; the reviewed MAI-only profile permits one bounded caBX provenance chunk); live
production activation followed a bounded exact-model output passing it. Do not
change the default Google parser or gate implicitly. Lifecycle regressions include MAI
cancellation/disconnect/worker failure, pre-dispatch release, post-dispatch fixed
ceiling charge, exactly-once lease/capacity cleanup and no delivery-start retry.

Pricing amendment: operator approved Sonnet USD 4/M input / USD 10/M output and
MAI USD 1 per bounded image request as local router estimates. Terra uses verified
Standard Global meter maxima USD 2.50 / USD 0.10 / USD 7.50 per million input /
cached / output tokens. Operator image estimates are not proven Azure billing
ceilings. Public MAI activation followed exact live output inspection during
restricted acceptance, before original public ingress was restored.
