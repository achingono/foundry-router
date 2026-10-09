# Schema diagnosis Risks

| Risk | Mitigation |
| --- | --- |
| Billing data leakage | Literal field/enums only; no IDs/names/amounts/error bodies |
| Diagnosis changes provider behavior | Unchanged bounded parser/cleanup; regression fixtures |
| Repeated requests | Durable started marker, OS lock, no retry/resume |
| Non-USD accepted as USD | Keep USD-only validation; new policy review if needed |
