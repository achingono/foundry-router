# Image-format risks

| ID | Risk | Mitigation | Status |
| --- | --- | --- | --- |
| I1 | Native decoder opens before dimensions checked | Pure bounded container preflight before Pillow | Design review pending |
| I2 | Metadata/animation expands work | Allow only baseline single-scan JPEG and one-chunk static WebP | Design review pending |
| I3 | Synchronous decode delays intake | Small pixel/input caps, segment cap, concurrent benchmark incl. scheduling | Open |
| I4 | Model-specific image cost differs | Existing explicit ceiling >=258 and token-price affirmation; live model gate separate | Open |
| I5 | Structural scan misses raster corruption | Vetted Pillow load after preflight; malformed fixtures | Open |
