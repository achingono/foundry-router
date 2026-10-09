# Quota risks

| Risk | Mitigation | Status |
| --- | --- | --- |
| Contention/hot row or row size | Bounded CAS, 256 records/48 KiB UTF-16 storage bytes, fail closed | Open |
| Lost acknowledgement causes duplicate dispatch | Retain uncertain ownership, typed error, readback recovery | Open |
| Expiry refunds dispatched work | Finalize estimate; explicit non-dispatch release only | Open |
| Clock skew causes early admission/reset | 70-second window, block midnight clock uncertainty, synchronized-host rollout assumption | Open |
| Settings rollout changes shared limits | Fingerprint gate, drain all writers; no destructive reset | Open |
| Storage outage silently allows traffic | Typed failure and API no-dispatch regression | Open |
| Local tests mistaken for scale-out acceptance | Keep live provider and deployed metrics/admission gates separate | Open |
