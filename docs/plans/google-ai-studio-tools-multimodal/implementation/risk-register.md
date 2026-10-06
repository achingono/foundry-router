# Implementation risks

| Risk | Mitigation | Status |
| --- | --- | --- |
| Required provider state lost | Explicit unsigned-only configuration; reject signature output | Open gate for signed tools |
| Underestimated image usage | Required model-profile token ceiling/pixel bound and token-price affirmation | Tested per profile |
| Parser memory/CPU growth | 2 MiB wire cap, encoded/decoded/pixel/item caps, bounded PNG raster decode and intake budget | Synthetic/client gates passed |
| Invalid generated arguments/JSON refunded | Existing billable failure settlement; validate before successful terminal events | Synthetic/client gates passed |
| Feature combination inferred | Separate explicit combination entries | Synthetic/client gates passed |
| Real compatibility unknown | No model-name inference, defaults off and separate live evidence | Live gate Planned |

PDF, native, audio/video, generated media and sealed continuation carrier decisions remain open.
