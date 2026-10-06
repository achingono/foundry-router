# Signed-server Responses JSON intake

**Planned**, 2026-10-05. Independent review before code.

The aggregate signed replay Linux benchmark sees raw request JSON parsing hold the event loop
for40.32ms; wholepath loop delay72.42ms. Source: ../signed-continuation/measurements.

1. Extend request_body with an API-owned offload_json flag, default false. The Responses route
   sets true only when its configured settings have a bound_history_required pool. Caller fields
   cannot select parsing behavior; ordinary servers and embeddings retain current behavior.
2. Stream and enforce existing raw Content-Length/byte/intake limits before parse. Capture immutable
   rawbytes. Use bounded_signed_work, no lease, with the original intake deadline to parse strict
   duplicate-free/nonfinite/work/depth bounded JSON offloop. At most two queued/running pureparser
   jobs share signed capacity; third busy request returns503 before admission. Timeout/cancellation
   shielding owns the slot until actual worker completion. No tool/media/config/provider work.
3. Parse task returns an owned dict, then existing model/stream/embedding semantic checks run.
   Request finally owns no parser capacity after completed parse. Signed request later acquires
   its lifecycle lease. Saturation during dispatch rejects new intake without provider requests;
   admitted leases reuse capacity and never reacquire. No unbounded await queue.
4. Test byte bounds, malformed/duplicate/nonfinite/depth JSON, timeout, saturation, no provider
   dispatch, ordinary default regression, auth/body key snapshot rotation and ownedbodymutation.
5. Focused/full coverage>=80%, Ruff/format/mypy, Docker, independent deep review; rerun profiled
   aggregate Linux8x100. Keep startup gate until all remaining signed/media/live gates pass.
