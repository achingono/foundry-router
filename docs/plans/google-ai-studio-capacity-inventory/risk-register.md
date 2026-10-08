# Google AI Studio capacity inventory risks

| ID | Risk | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- |
| R1 | Test caps/context windows mistaken for quotas | Overstated capacity | Null quota fields, explicit source/date requirement | Open |
| R2 | Discovery interpreted as entitlement or free-tier approval | Invalid or paid dispatch | Preserve manifest classification and live outcomes separately | Open |
| R3 | Alias/model buckets double-counted | Over-admission | Unknown bucket identity; require provider-confirmed sharing | Open |
| R4 | Small historical samples presented as reliability guarantee | Poor routing decisions | Exact counts, dated observations, no statistical claim | Open |
| R5 | Unknown usage counted as failure or zero thinking | False conclusions | Narrative-backed outcomes, retain thought metadata limitation | Open |
