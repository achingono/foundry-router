# Pricing evidence

**Checked:** 2026-10-29. **Scope:** public USD retail rates and the available current-cycle usage/pricesheet evidence. This does not establish account-specific negotiated rates or a production budget.

## GPT-6.1-terra

The Azure Retail Prices API East US USD query returned 1,322 rows across two pages (1,000 plus 322; no further page). Its filter was `contains(productName,'OpenAI') and armRegionName eq 'eastus'`. The GPT6 product has these Global Standard meters, effective 2026-10-01; prices are USD per million tokens:

| Context meter | Input (`Inp`) | Output (`Opt`) | Cached input (`Cd Inp`) | Cache write (`Cd Wr`) |
| --- | ---: | ---: | ---: | ---: |
| Short context, Global Standard | $1.00 | $5.00 | $0.05 | $1.25 |
| Long context, Global Standard | $2.00 | $7.50 | $0.10 | $2.50 |

The meter names distinguish short and long context, but the retail records do not state the context cutoff. The captured East US catalog contains 16 `61 terra` rows; all are Standard Global or Standard Data Zone. It contains no Terra Global Priority meter, so no Priority rate or billing dimension has been verified. The existing service-tier pass-through does not supply that missing rate.

The sanitized current-cycle Azure usage capture contains no GPT-6.1-terra meter rows; its Terra rows are for another model. It therefore cannot confirm the price charged to either project. A subscription pricesheet lookup did not yield rates: `az consumption pricesheet show` and a direct Microsoft.Consumption pricesheet request both returned 404 responses stating cost-management data was unsupported for that subscription/API version. No account-effective Terra rate was obtained.

## Claude Sonnet 5.5 on Azure Foundry

The East US Azure Retail Prices API returned zero rows for filters matching `Claude` or `Sonnet` in meter names and `Anthropic` or `Claude` in product names. The captured current-cycle usage rows also contain no Claude/Anthropic meter. The Azure subscription pricesheet lookup described above did not provide an account-specific rate.

Anthropic's official first-party API pricing page lists Claude Sonnet 5.5 at **$2/M input tokens** and **$10/M output tokens**. It lists cache-write rates of **$2.50/M** for 5-minute writes and **$4/M** for 1-hour writes, plus **$0.10/M** for cache reads. These are Anthropic API prices; they do not establish the Azure Foundry deployment's billable rate and must not be substituted for it.

**Azure Foundry Claude pricing remains unverified.** An Azure-specific price record or actual billable usage is required before an exact Azure credit estimate can use these rates.

## MAI-Image-2.6 Global Standard

The same East US USD retail capture contains these Global Standard meters, effective 2026-09-01:

| Meter | Retail rate |
| --- | ---: |
| `Image 2.6 Text Input Glbl 1M Tokens` | $5/M tokens |
| `Image 2.6 Image Output Glbl 1M Tokens` | $38/M tokens |

Microsoft's [MAI image API documentation](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) specifies a PNG image in `data[].b64_json`. It permits 1024×1024 output and documents a 2,359,296-pixel maximum for Image 2.6, but it does not return usage counters or define how many billable image-output tokens correspond to an image or pixel count. The retail meter is token-priced, not per-image.

Consequently, these rates do **not** determine a fixed 1024×1024 image cost or a defensible positive per-image ceiling. No token-to-image conversion, billable output-token bound, or per-image tariff was found in the cited contract or catalog. If the feature uses a fixed image reservation, that ceiling needs an independently approved operator value or further authoritative Azure billing evidence; it must not be described as a measured image price.

## Sources and limits

- [Azure Retail Prices API](https://prices.azure.com/api/retail/prices): USD East US queries described above; records identify meter names, units, effective dates, and retail unit prices.
- [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing): first-party Claude API pricing only.
- [MAI image API contract](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image): image request limits and response format.
- Private captures used for this check: `/private/tmp/router-retail-prices.json`, `/private/tmp/router-retail-prices-page2.json`, `/private/tmp/router-claude-meter-prices.json`, `/private/tmp/router-historical-rates.json`, and `/private/tmp/mai-image-docs.md`. Raw captures are not included in the repository.

No inference, billable probe, deployment, or cloud mutation was performed for this pricing check.
