**Approved for the nine fresh bounded staging calls, once**, using the reviewed Vertex-time packet. No Critical or Major blocker found in this scope; one nonblocking timestamp finding remains.

The public manifest exactly matches the runner-generated `VERTEX_RUN` manifest and packet fingerprint: **ca5**, **Linux/amd64**, digest `sha256:4153217d61a7a803c4f0c2d2969b2c01d6cffe4014f4367593b507c1850bd4e4`. Both historical manifests retain identical cases, requests, prices, timeouts and reserve. Staging arithmetic is **0.100000 − 0.000018 − 0.004000 − 0.000468 = 0.095514 USD**; production remains **9.90 USD**, as local estimates. Failed or ambiguous slots halt execution and cannot replay.

**Suggestion — timestamp offset validation:** [google_native.py:70](../../../src/foundry_router/api/adapters/google_native.py) accepts invalid RFC3339 offsets such as `+00:60` and `-04:99`; `datetime.fromisoformat()` normalizes them. Static checks and existing tests miss that parser behavior. Impact is limited to accepting malformed, discarded metadata. Explicitly constrain offset minutes to `00–59` and add rejection cases across all three envelope paths.

Both prior operational Majors are **remediated in code**:

- Successful empty replica enumeration is required for every inactive revision before preparation and immediately before promotion.
- Preparation verifies the barrier’s snapshot hash and process identity; the handoff binds snapshot, barrier, stopped proof, seeds, payload/configuration, image and manifest, with promotion rechecks.

**Production remains conditional** on nine staging passes, stopped staging, actual admission-barrier continuity, unchanged memory process through drain, stopped old writers, verified handoff bindings and production acceptance. Those operational outcomes were not independently observed here.

The measured full log confirms **2,692 passed, 3 skipped, 19 deselected, 90.23% coverage**. Focused/runner results, lint, format, mypy and build/readiness outcomes remain supplied evidence; Sonar’s script is absent.

Historical preflight was reviewed as code only; its private inputs were unopened. No edits, inference calls or subagents were used. `createTime` remains a compatibility hypothesis—the actual unknown field name is unproven, and live acceptance must establish compatibility.