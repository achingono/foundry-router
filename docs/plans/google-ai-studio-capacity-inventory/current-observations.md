# Current direct text observations

**Partially implemented**, observed 2026-10-08. One small survey probe per project/model followed by bounded ramps on completed combinations. Provider quota rejections are reported separately from other failures; all values are historical sample observations, not reliability guarantees. Thinking profiles vary and are stored per attempt in source JSON. Native router and streaming evidence remain separate.

| Model | Survey completed / 5 | Ramp completed | Ramp 429 | Ramp other failed/ambiguous | Median completed latency (s) |
| --- | --- | --- | --- | --- | --- |
| `gemini-2.5-flash` | 2 / 5 | 12 | 2 | 0 | 0.437 |
| `gemini-2.5-flash-lite` | 2 / 5 | 0 | 0 | 0 | 0.402 |
| `gemini-2.5-pro` | 0 / 5 | 0 | 0 | 0 | Unknown |
| `gemini-3-flash-preview` | 5 / 5 | 30 | 5 | 0 | 0.91 |
| `gemini-3.1-flash-lite` | 5 / 5 | 26 | 0 | 5 | 0.595 |
| `gemini-3.5-flash` | 5 / 5 | 32 | 5 | 0 | 0.854 |
| `gemini-3.5-flash-lite` | 0 / 5 | 0 | 0 | 0 | Unknown |
| `gemini-3.6-flash` | 5 / 5 | 30 | 5 | 0 | 1.01 |
| `gemini-3.7-flash` | 3 / 5 | 2 | 0 | 3 | 5.158 |
| `gemini-3.8-flash` | 5 / 5 | 10 | 0 | 5 | 4.087 |
| `gemini-robotics-er-2-preview` | 5 / 5 | 30 | 5 | 0 | 1.157 |
| `gemma-4-26b-a4b-it` | 4 / 5 | 39 | 0 | 4 | 1.349 |
| `gemma-4-31b-it` | 0 / 5 | 0 | 0 | 0 | Unknown |

Sources: [survey](free-tier-survey-2026-10-08.json), [model ramps](model-rate-ramps-2026-10-08.json). The earlier 2.5 Flash-Lite ramp is recorded separately in the [inventory](index.md); zeros in its ramp columns above mean that model was intentionally excluded from the later model-ramp stage.

3.5 Flash-Lite failed all fresh probes after historical success. 3.7/3.8 Flash and Gemma encountered intermittent capacity/timeout failures. Small successful probes on 3.1 Flash-Lite were followed by timeouts in every project ramp. 3 Flash Preview and 3.5/3.6 Flash completed bursts up to explicit quota rejection; this does not establish behavior on substantive workloads.
