---
name: find-toy-lookalike-competitors
description: Find and tier visually similar Amazon toy competitors using product titles, images, sales evidence, and parent-family deduplication. Use when a user provides an Amazon toy URL or ASIN and asks for strict lookalikes, all visually similar competitors, layered competitor markets, missed top sellers, visual market coverage, or a toy competitor report where same-need or same-category products are too broad. Require amazon-scraper-vps for every Amazon page and image request; use SellerSprite MCP when available for sales and related-product evidence.
---

# Find Toy Lookalike Competitors

Find the market defined by exterior similarity, not merely shared function, need, keyword, or Amazon category. Let titles discover candidates; let images decide membership.

## Safety boundary

- Invoke `$amazon-scraper-vps` before any Amazon collection.
- Send every Amazon page and image request through its authenticated VPS API with proxy routing.
- Never access Amazon locally with a browser, web search, `curl`, `Invoke-WebRequest`, Playwright, or the user's IP.
- Stop if VPS health is not `status: ok` or `proxy_configured: true`; never fall back to local access.
- Download Amazon images only through the VPS `/image` endpoint. Show only saved local images, never Amazon CDN URLs.
- Keep tokens, proxy credentials, cookies, and passwords out of files and output.
- Use SellerSprite MCP directly for sales, categories, traffic relations, and parent/variation evidence; it does not replace image inspection.

## Operating principles

1. Title and structured data create the candidate pool.
2. Product images determine the visual tier.
3. Sales data checks whether important products were missed; high sales never promote a visually different product.
4. Group variants by parent ASIN before counting market size.
5. Treat missing fields as unknown. Do not invent prices, sales, parent ASINs, or ratings.
6. Use “候选发现” or “覆盖检查” in Chinese output. Do not use the Chinese term “召回”.
7. Preserve candidate lineage. A discovered ASIN must never disappear between discovery, visual review, sales enrichment, and final output without a recorded decision.
8. Separate the strict lookalike market from the broader operating market. Theme substitutions that keep the same physical play architecture belong in the market audit and may become Tier 3; they must not be lost merely because the seed title uses a narrower animal, vehicle, or character word.

## Public installation paths

Commands below use `/opt/codex/skills` as a generic installation root. A custom
Runner must bind its allowed commands and evidence checks to the actual installed
paths before execution. This repository does not include that external Runner.
Do not bypass its evidence checks or claim a standalone end-to-end workflow is
validated merely because these scripts are present.

## Token-efficient stage contract

Reduce repeated context, never evidence. Keep the same discovery depth, mandatory high-sales review cohort, image checks, and family validation while separating the work into durable stages:

1. Persist discovery, manifest, image ledger, visual verdicts, family evidence, exact-month sales, and final result as independent checkpoints.
2. A later-stage failure must resume from its own checkpoint. Sales, report, or upload repair must not repeat Amazon discovery, image download, or an already verified visual pass.
3. Prefer the supplied deterministic scripts for ASIN extraction, source union, deduplication, image download, conservation checks, parent grouping, and report assembly. Do not ask the model to restate large raw JSON or logs when a digest-bound artifact is available.
4. Give a classification pass only contact sheets, the cell mapping, and one short title per candidate. Do not include URLs, sales, discovery logs, previous verdicts, or full product records.
5. Keep SellerSprite enrichment separate from visual judgment. Use small isolated exact-trend batches so one slow ASIN cannot invalidate a large batch, and reuse every batch whose task-bound log still proves the exact ASIN set, marketplace, and month.
6. Repair only the missing ASINs or invalid artifact named by the Runner contract. Never broaden a repair into a fresh market search for convenience.
7. Count cached and uncached input separately in usage reporting. A large cached transcript is still a cost and is not permission to carry unrelated prior-stage context forward.

These rules optimize execution, not coverage. Never lower the requested scan/review targets, skip high-sales exclusions, or replace image judgment with title screening to save tokens.

## Workflow

### 1. Establish the target fingerprint

Scrape the target detail page through the VPS and save its main image locally. Record:

- ASIN, title, price, rating, reviews, bought-past-month, category, bullets, and image;
- main silhouette and shell type;
- visible storage, attachment, opening, or carrier structure;
- number and arrangement of included pieces;
- theme, color family, interaction, size, and pack format.

Write a one-sentence visual definition before searching. Separate mandatory visual features from optional details. Read [references/tiering-rules.md](references/tiering-rules.md) before the first image judgment in a task.

### 2. Build independent candidate paths

Generate multiple query families instead of one broad keyword:

1. exact composition: object + count + distinctive structure;
2. structure synonyms: carrier, storage, folding, transforming, cage, tray, shell, or the applicable equivalents;
3. silhouette: body type + child pieces + theme;
4. title variants: hyphenation, number words, common category synonyms;
5. related products: target traffic listings, frequently-bought-together, viewed-also-viewed, and sponsored relations;
6. category sales audit: relevant toy nodes sorted by estimated monthly units.

For a theme-specific target, add one theme-neutral structure query and the most plausible adjacent-theme queries. For example, a hard-shell robot cat also requires robot-pet and quadruped robot-toy paths; dog, unicorn, or another theme is a broader-market candidate, not an automatic visual match.

Use one standalone `/usr/bin/python3 /opt/codex/skills/find-toy-lookalike-competitors/scripts/vps_search_candidates.py` command for Amazon searches. Pass `--seed-asin` with the exact Runner-supplied source ASIN, `--pages 3`, at least four `--query` values, and `--output outputs/amazon-search-candidates.json`; do not prepend environment assignments or chain another shell command. The script emits a content digest and seed identity that the Runner verifies. Use up to 5 pages only when the Runner task explicitly requests deep expansion. Deduplicate by ASIN.

Merge every discovery source into `outputs/candidate-manifest.json` before screening. The manifest is the immutable ASIN inventory for the task. Preserve the source queries and source types for each ASIN.

Write the raw Amazon search union to `outputs/amazon-search-candidates.json`. The Runner compares that file and the ASINs actually returned by SellerSprite discovery calls with the final manifest. Do not reconstruct a smaller list by hand.

After the first visual pass and before the authoritative independent visual pass, call SellerSprite `asin_detail` for one representative of every provisionally selected Tier 1, Tier 2, or Tier 3 Amazon family. Do not query excluded candidates merely because their images were reviewed. Each `asin_detail` request contains only the exact `asin` and `marketplace`; never add `returnFields` or discovery/pagination fields. When the parent is not yet known, query the selected ASINs needed to establish the complete selected families, then deduplicate the ledger by verified family. Use the returned `parent` and complete `variationList`; a listing whose verified parent is null is a singleton family. Write `outputs/family-variation-candidates.json` as `{schemaVersion:1,checkpointComplete:true,queries:[{representativeAsin,parentAsin,tool:"asin_detail",resultStatus:"SUCCESS",children:[...]}],candidates:[{asin,parentAsin,title}]}`. Include a query row only when its matching tool call succeeded. `candidates` is exactly the union of every query's complete child list. Keep each child ASIN in the manifest and decision ledger. If the later isolated visual review promotes a previously excluded candidate, keep its parent unknown unless task-bound evidence already proves it; do not force detail calls for every excluded image merely to cover this rare promotion.

For SellerSprite, normally inspect:

- `asin_detail` for target category and parent information;
- `traffic_listing_stat` followed by selected `traffic_listing` relations;
- `traffic_keyword` once for the seed, sorted by traffic percentage, to discover the seed's real high-traffic phrases;
- `competitor_lookup` for exact phrases, structure phrases, and relevant toy nodes, sorted by `total_units`;
- ASIN batches of at most 40 to fill sales and parent fields for image-selected products. This is a per-request SellerSprite limit, never a limit on the visual shortlist or final market.

Treat `traffic_keyword` as a keyword-discovery source, not an ASIN inventory. Its optional `topAsins` field may be null even when requested. Never depend on that field for coverage. Select only phrases that preserve the target's physical object or play structure, then run those phrases through `competitor_lookup` or `product_research` with phrase matching and the requested month. Include at least one seed-derived structural phrase among the ranked market paths. Broad traffic words that describe only a brand, age, animal theme, or general toy need are not structural phrases.

After the first visual pass, use confirmed Tier 1 or Tier 2 families to identify at most one additional meaningfully different structural phrase when they reveal vocabulary absent from the seed. Run only that bounded second-hop path. Stop expansion when it adds no new Tier 1 family; do not recursively expand from Tier 3 or excluded products.

Use SellerSprite market queries with variations included during discovery. Preserve every returned child ASIN; grouping by parent happens after discovery and must not delete children.

Do not use an unrestricted marketplace query for ambiguous words such as `carrier`. Require a toy node or strong toy/context terms.

### 3. Protect high-sales coverage

Read [references/coverage-evidence.md](references/coverage-evidence.md) before running the market audit. Unless the caller requests a different range, use these depth targets:

- quick: scan at least 100 sales-ranked rows and visually review 25 market candidates;
- standard: scan at least 200 sales-ranked rows and visually review 150 market candidates;
- deep: scan at least 400 sales-ranked rows and visually review 100 market candidates.

Every sales-ranked SellerSprite request uses `marketplace=US`, the requested month, `variation=N`, `order={field:"total_units",desc:true}`, and `returnFields="asin,title,units,imageUrl,parent"`. Every keyword path uses `matchType=1` for phrase matching, or `keywordEqual=true` when exact matching is intentionally required; never run a broad keyword path. Use `keyword`, not `keywords`, with `product_research`. A keyword-free path must use a specific relevant toy `nodeIdPath`. The current SellerSprite MCP exposes numeric monthly volume as `units`; requesting the documented `totalUnits` projection can turn that value into null. Pages start at 1 and remain consecutive within each path. Bind each request to the response's `page`, `size`, `pages`, `total`, `hasNextPage`, or equivalent terminal metadata; a short deduplicated page alone is not proof of exhaustion. Reject contradictory pagination metadata. The response may echo `order.field` as blank even when the requested ordering was applied; do not stop for that echo alone when the request and pagination are valid. Globally sort distinct returned ASINs by numeric `units` or legacy `totalUnits` descending; put unknown values after known values and preserve API order for ties. The exact ranked review prefix for the chosen depth must be image-reviewed. Do not use title screening to skip an early ranked ASIN. For standard and deep work, aim to return at least 50 genuinely qualifying child ASINs: review the ranked cohort in batches and keep expanding the image-reviewed prefix until 50 qualify or the scan target has been visually exhausted. This is a coverage target, never permission to promote a category-only or theme-only mismatch. Continue until at least the scan target of distinct ASINs is reached. If fewer rows exist, prove every ranked path is on its real terminal page, review every returned ASIN, and record the evidenced shortfall.

Create the visual shortlist as the union of:

- high structural-title matches;
- products appearing in multiple independent paths;
- top-selling products from tightly scoped relevant toy searches;
- suspicious boundary products that could reveal a missing design family.

Always inspect the images of the relevant high-sales products even when their titles score poorly. Document why each high-sales exclusion fails the visual definition.

The Amazon seed, SellerSprite traffic candidates, expanded family variations, and the recorded sales-audit review cohort cannot use `screened_out`; they require image review and a Tier 1, Tier 2, Tier 3, or `excluded` decision. When the user or an operator supplies an ASIN comparison list, add it as `operator-audit`, inspect every item, and record a decision. Supplied ASINs are evidence to audit, not automatic inclusions.

Before visual decisions, write `outputs/image-review-candidates.json` with every candidate that will be image-reviewed and the exact, unmodified image URL returned for that ASIN by the verified VPS inventory or a successful, task-bound SellerSprite response. Do not use `competitor_lookup` with an `asins` array as an exact-ASIN image lookup: it returns a related-product market and can introduce unrelated rows. First reuse an exact URL already observed for the same ASIN. If a mandatory candidate still has no URL, call `asin_detail` for that exact ASIN with only `asin` and `marketplace`, or run one standalone `/usr/bin/python3 /opt/codex/skills/amazon-scraper-vps/scripts/call_vps.py scrape "https://www.amazon.com/dp/ASIN"` command. Require the returned main ASIN to equal the requested ASIN, and copy its exact returned image URL without changing resolution markers, path segments, or query parameters. Family evidence remains subject to the complete `asin_detail` variation checks above even when an exact detail image is usable. If none produces an exact URL, leave the candidate unresolved and fail the coverage check; never invent or normalize a URL. Run one standalone `/usr/bin/python3 /opt/codex/skills/find-toy-lookalike-competitors/scripts/vps_download_images.py --input outputs/image-review-candidates.json --image-dir outputs/images --output outputs/image-download-ledger.json` command. Never prepend environment assignments, pass `--client`, chain commands, pre-create files, reuse old files, or download by another route. Copy each ledger `localImagePath` to the matching manifest candidate. The Runner verifies the command, ledger digest, ASIN-to-source-URL binding, true image format and extension, filename, file bytes, dimensions, and task-local path.

Continue searching until both conditions hold:

- two new, meaningfully different query families add no new first-tier product family;
- all relevant high-sales products in the chosen audit range have been visually checked.

State the chosen audit range; do not claim literal completeness across all Amazon listings.

### 4. Download and review images

Keep source image URLs exact and internal. Use `scripts/vps_download_images.py` for a fresh download through the VPS with checkpoint support; the script records the exact `sourceImageUrl` for Runner verification.

For every item reported as `imageReviewed: true`, preserve the real downloaded in-task path as `candidate.localImagePath`. The Runner verifies the file signature and rejects paths outside the task directory.

Build contact sheets with `scripts/build_contact_sheet.py`. Keep the target in the first cell with a red border. Show only the cell number and exact ASIN on the sheet; provide one compact title per candidate in the accompanying mapping, while omitting URLs, prices, sales, discovery logs, and earlier tiers. Put no more than 25 candidates on one sheet and paginate additional candidates.

Run the authoritative visual pass in a separate read-only working directory that contains only the rendered contact sheets, the cell-to-ASIN mapping, and the minimal visual output schema. It must not receive or be able to read the first-pass result, titles, sales, discovery logs, or earlier verdicts. Require one decision for every mapped ASIN, then merge only the visual fields back into the preserved research record.

Every manifest ASIN must receive exactly one decision:

- `screened_out` for a structured/title rejection made before image review;
- Tier 1, Tier 2, Tier 3, or `excluded` after image review;
- `seed` only for the Amazon target when it appears in the manifest.

Use `tier_1`, `tier_2`, and `tier_3` only in decision outcomes. In final product rows, write the corresponding display values exactly as `Tier 1`, `Tier 2`, and `Tier 3`. Write the final result `dataMonth` as `YYYY-MM`; compact `YYYYMM` is only for SellerSprite request parameters.

Selected and excluded products must have `imageReviewed: true`. Do not use a score cutoff, contact-sheet page limit, SellerSprite batch size, or missing SellerSprite row to silently discard an ASIN.

The manifest must use the coverage-evidence schema and record the sales-ranked review cohort plus the last two saturation queries. Use the exact final two VPS Amazon query strings, in order, as the two `stoppingEvidence.queryFamily` values. The Runner rejects a task if a raw Amazon candidate, expanded variation, SellerSprite discovery candidate, or operator-audit ASIN is absent from the manifest, or if a mandatory audit item lacks a verified downloaded image and image decision.

For a coverage repair, treat the prior Amazon query list as immutable. When the Amazon artifact and its command evidence are already valid and the defect is in SellerSprite coverage, family evidence, or bookkeeping, reuse that artifact and do not repeat Amazon search. If Amazon evidence itself must be repaired, rerun the exact same strings in the exact same order and do not add, remove, rename, or reorder a query. Preserve the complete cross-attempt source union. When the Runner supplies a repair requirements file or a prefilled manifest/base result, extend those artifacts instead of rebuilding a smaller shortlist. Programmatically safe `screened_out` rows may be prefilled only for candidates outside the mandatory image-review set; never invent a visual verdict for a mandatory candidate. If the Runner prefills `outputs/image-review-candidates.json`, preserve every prefilled ASIN and its exact verified URL. Add only the listed unresolved ASINs after obtaining exact-ASIN evidence, then run the VPS downloader against the full combined file. Never replace the prefilled image inventory with the smaller list from an earlier attempt. Reuse an already verified family-variation artifact during any non-family repair. Call `asin_detail` only for the exact missing or invalid representative ASINs listed by the repair contract; never additionally query a returned parent ASIN.

### 5. Assign the three market tiers

Use the rules in [references/tiering-rules.md](references/tiering-rules.md):

- Tier 1 — 核心外观市场;
- Tier 2 — 扩展外观市场;
- Tier 3 — 外围结构市场;
- Excluded — same need/category but no meaningful exterior relationship.

Require silhouette and primary structure for Tier 1. Never assign a tier from title alone. When uncertain, place the product in the broader tier and state the deciding question for the user.

Record judgments in a decision JSON and run `scripts/compile_tiers.py`. The decision inventory must cover every ASIN in `outputs/candidate-manifest.json`. Use parent ASINs to flag cross-tier variants and prevent double-counting.

### 6. Validate sales and families

After visual judgment, batch all selected ASINs through SellerSprite `competitor_lookup` to fill price, rating, BSR, and supporting parent evidence. Use as many batches as required, with at most 40 ASINs per request. Keep every selected ASIN even when SellerSprite omits it; leave unavailable fields null and record the missing ASIN in data-quality output.

For every selected ASIN, call SellerSprite `asin_sales_trend` for the requested month. Only its exact `parentUnitSales` and `parentSalesRevenue` fields may populate parent-family sales, and only its exact `childUnitSales` may populate child sales. Never relabel `competitor_lookup.totalUnits` or `totalAmount` as parent-family metrics, even when values repeat across children. Require the returned ASIN to equal the requested ASIN; treat a null trend series or absent exact-month point as valid no-data, while mismatched or failed calls remain null and are recorded. Normalize ASINs with trim and uppercase, and use the child ASIN as the grouping key only when no valid parent is returned.

Keep two separate family concepts:

- `parentAsin` for verified Amazon variation relationships;
- `visualFamilyId` for the same or unmistakably related mold across unrelated Amazon parents.

Normalize SellerSprite's verified singleton sentinel `parentAsin == asin` to `parentAsin: null` only when the detail response proves a singleton (no variations, or one self variation). Keep a self-parent value when a complete multi-child variation list proves that the representative is also the family parent.

Do not sum:

- the same ASIN twice;
- child ASINs when the metric is repeated at parent level;
- the same parent family across multiple tiers without an explicit family-level rule.

If family-level units cannot be verified, present product estimates individually and label the market total unavailable.

### 7. Deliver the result

Follow [references/output-schema.md](references/output-schema.md). Lead with the three contact sheets, then report:

- target visual definition;
- product and family counts by tier;
- top products by estimated monthly units within each tier;
- high-sales products inspected but placed in Tier 3 or Excluded;
- scanned/reviewed coverage counts and any operator-audit ASINs that were excluded;
- parent-family overlaps and data month;
- unresolved boundary decisions for the user.

Do not mix Tier 3 into direct-competitor totals. Keep local image and JSON artifacts available for review.

## Scripts

- `scripts/vps_search_candidates.py`: run multi-query Amazon searches through the proxy-enforced VPS.
- `scripts/merge_candidate_sources.py`: merge normalized Amazon and SellerSprite exports by ASIN.
- `scripts/vps_download_images.py`: fresh VPS image download with per-item checkpoints and a verifiable digest.
- `scripts/compile_tiers.py`: apply human/agent visual decisions and flag parent-family overlaps.
- `scripts/build_contact_sheet.py`: render target-plus-candidate image sheets for review.
