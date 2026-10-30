# Responses Request Limit Inputs

Status: **Planned**. User authorized matching production request intake to downstream limits after a new image-reading conversation received HTTP 413.

| Input | Source | Notes |
| --- | --- | --- |
| Azure Responses image limit | https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses?view=foundry-classic | Retrieved October 15, 2026: combined prompt/images under 512 MB; not the Chat Completions 20 MB image limit. Use conservative decimal 512,000,000 bytes. PDF and model/context limits remain provider-owned. |
| Current intake | src/foundry_router/config/__init__.py; api/common.py | Default 2 MiB, configurable ceiling 100,000,000; production has no override. |
| Cost estimation | src/foundry_router/credit.py | Independent 2,000,000-character/serialized-byte bound blocks larger inline images. Preserve conservative byte/character accounting and depth controls. |
| Production state | Read-only control-plane and admin observations | Memory, one worker/replica; 0.5 GiB deployment requires resource sizing and bounded concurrency. Current account seeds must not be replayed after restart. |
