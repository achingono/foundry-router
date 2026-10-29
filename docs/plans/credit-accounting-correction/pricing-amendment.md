# Verified pricing and allowance amendment

Status: **Planned**, revised after independent pricing review identified priority-tier forwarding. Independent re-review requested before live preparation/mutation. No runtime source change.

Historical Microsoft.Consumption usageDetails API (2024-08-01) returned all pages: 84 fs-swarm resource rows for October 2–29, total 129.042759285861 CAD, latest date October 26; no fs-openclaw rows for its October 26 cycle. Meter IDs matched public Microsoft Retail Prices API records for the configured six OpenAI model identities, eastus, GlobalStandard. The earlier text search included a `gpt` prefix absent from meter names and missed these records. UnitPrice=0 and zero historical sol cost are not safe future rates; matched public rates are USD/1M tokens. Current GlobalStandard model identities and versions match both accounts.

The catalog includes distinct ShortCo/LongCo, cache-write and priority-processing rates. Azure passes caller service_tier through, so GlobalStandard deployment SKU does not exclude priority processing. A single per-pool local estimate cannot infer actual prompt context class, selected processing tier or cache-write usage. Rather than configuring only the cheapest short-context cached rate or retaining underpriced ordinary/output dimensions, use the maximum observed applicable Standard Global and Priority Processing Global rate for each dimension: ordinary-input estimate covers both uncached input and cache creation; cached input uses the maximum cached-read price; output uses maximum context/tier output. Priority rows exist for GPT5.6; the complete 168-row capture has none for these GPT6 models, so their rates are not speculatively doubled. These are conservative local ceilings over the verified catalog rows, not exact provider bills. No new context/tier inference, schema, automatic billing provider, historic refund or pool is added.

| Pool | Input ceiling USD/M | Cached input ceiling USD/M | Output ceiling USD/M |
| --- | ---: | ---: | ---: |
| gpt-5.6-luna | 1.00 | 0.08 | 3.60 |
| gpt-5.6-terra | 10.00 | 0.80 | 36.00 |
| gpt-5.6-sol | 20.00 | 1.60 | 60.00 |
| gpt-6-luna | 0.25 | 0.02 | 0.75 |
| gpt-6-astra | 25.00 | 2.00 | 75.00 |
| gpt-6.1-sol | 5.00 | 0.20 | 15.00 |

Operator confirmed fs-openclaw allowance CAD200/current remaining CAD180. Bank of Canada latest daily FXUSDCAD on October 28, 2026 is 1.4036 CAD/USD; conservative cents-floor conversion gives USD142.49 allowance and USD128.24 remaining. Cycle remains day26. Other account allowances/cycle days/reserve policies are preserved; remaining estimates come from the final drained old-process snapshot, never old startup values. This amendment authorizes preparing the above exact monetary configuration once independently reviewed; production mutation still requires the exact packet, image and all handoff gates.

Acceptance should verify all six pricing triples and fs-openclaw allowance/seed in the loaded new process, effective spendable credit, canonical counter startup zero and no old writers. One bounded nonstream/stream synthetic pair in gpt-6.1-sol may validate settlement: max_output_tokens128, at most128 estimated input tokens, store=false, no retries, 60-second total/request. Worst-case pair <=0.01USD at the conservative ceilings. Abort after any failed or ambiguous result; do not replay. The acceptance pair is part of the user's requested deployed accounting correction, and must be bound in the concrete packet before inference.

Raw meter rows, catalog IDs and resource identities remain local under /private/tmp. Published source: https://prices.azure.com/api/retail/prices (USD, actual meter-ID matching); FX source: https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1. Historical credits and billing completeness are not inferred from these list prices.
