# HTTP diagnosis Risks

| Risk | Mitigation |
| --- | --- |
| Error body/headers disclose billing IDs or auth | Record only status integer and validated numeric Retry-After; no bodies |
| Repeated probes worsen throttling | One durable consumed invocation, no retries or extra probes |
| Observer changes acceptance | Return unchanged response, no parsing/body read; normal provider decides |
| Status overclaimed as authorization diagnosis | Record exact status and scoped interpretation only |
