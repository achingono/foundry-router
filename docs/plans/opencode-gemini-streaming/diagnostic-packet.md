# Streaming diagnostic packet (DRAFT)

Status: **Final, pending independent final review before dispatch**. Private packet file: `stream-diagnostic-packet.json` under the release work area, SHA-256 `db75fda4205db6e3b01c1dfa317eb5e4fcdf90064eb7d5e2bd6ace348dc8e646` (supersedes `14581efb…`: the funds pin is now the canonical-JSON hash `8f6da628…` matching what the executor computes, not the raw-file hash). This record contains hashes and amounts only; no credentials, prompts, outputs or container IDs.

## Pins

- Identity: `opencode-gemini-flash-stream-diagnostic-v1`
- Executor: `60489ae98fa48b3baafdaf2c160f7915e02b12e38e36f37dc7b8df10c67fb732`
- Dependencies: `google_native e2177a95…06c57238b`, `google_ai_studio 5969381d…b50b0e4ae577`, `openai_compatible c8863166…71000971a`, `google_schema b98c7035…6a734f92f023`, `google_tools 91f92b0f…c2da104afc`, `five_validation 7fca6826…39cea3ff` (working-tree harness with the new streaming identity)
- Funding: R 0.104, D 0.004, S 0.10. Fresh operator-authorized staging funds, separate from ca6 history; production 9.90 unchanged.
- Request: `3d586df5…64d75a`; native body: `d916dcf1…3efe5e`; route `.../models/gemini-3.8-flash:streamGenerateContent?alt=sse`; low thinking with thought-inclusive pricing at 1.50/7.50 per million.
- ca6 history: manifest `7d30655f…bf94cb` (matches the previously pinned public artifact), ledger `a54d4e76…43d6bceaaeb`, snapshot `3e7baec5…08ef6715516a`, stopped proof `02c44acd…36202533834`, container-id hash `3fcd62d6…349f96da` (hash only). Sources: `runner5/manifest.json`, `runner5/identity.json`, `runner5/ledger.json`, `staging5-final-admin.json`, `staging5-stopped.json`, `stage5-container-id.txt`.
- ca6 reconciliation: seven staging debits sum 0.01787075; 0.088 − sum = 0.07012925 matches the final snapshot with zero reservations.

## Remaining gate before dispatch

`funds_snapshot_sha256` is now bound (`9d15030e…`, captured from the live isolated funds-holder `zen-five-funds-20261014` running the ca6 image with exactly 0.104 and zero reservations; all historical staging writers verified exited). A final independent packet review of the provisioned state and writer exclusion is required before any dispatch. The executor refuses to run until every pin matches.
