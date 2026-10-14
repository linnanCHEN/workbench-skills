---
name: find-toy-lookalikes-from-product-image
description: Turn a toy product information image, packaging image, catalog sheet, or product collage into a three-tier Amazon lookalike market. Use when the user has no Amazon seed URL or ASIN and instead supplies an image containing a toy, model number, brand, specifications, variants, dimensions, functions, or accessories, then asks to find the same product, same mold, visually similar products, or the corresponding Amazon market. Extract printed facts and visual structure separately, search Amazon only through amazon-scraper-vps, and apply the find-toy-lookalike-competitors three-tier method.
---

# Find Toy Lookalikes from Product Image

Convert a supplier or product-information image into a structured source fingerprint, then find and visually tier the corresponding Amazon toy market. The source image remains the canonical target even if an Amazon anchor listing is found.

## Dependencies and safety

- Inspect the supplied local image with `view_image`; do not use image generation.
- Invoke `$find-toy-lookalike-competitors` for candidate discovery, image download, three-tier judgment, parent-family handling, and output format.
- Any coverage-repair pass inherits the first Skill's immutable-query and deterministic-scaffold rules. Reuse an already valid VPS Amazon artifact without rerunning it; if its evidence itself is invalid, rerun the original query strings in the same order. Extend the Runner's prefilled artifacts and do not restart from a smaller candidate shortlist. When the Runner prefills `outputs/image-review-candidates.json`, preserve every ASIN and exact verified URL, append only unresolved exact-ASIN rows, and never shrink it to an earlier image list. Reuse verified family evidence during non-family repairs; if the contract requires family repair, call only its listed representatives and never add a returned parent ASIN as an extra lookup.
- Invoke `$amazon-scraper-vps` before any Amazon request.
- Send every Amazon page and image request through the authenticated, proxy-configured VPS service.
- Never access Amazon locally with a browser, web search, `curl`, `Invoke-WebRequest`, Playwright, or the user's IP.
- Show only local images saved through the VPS `/image` endpoint. Never expose Amazon CDN image URLs.
- Use SellerSprite MCP when available for sales, categories, related products, and parent/variation evidence.
- Stop if the VPS is unhealthy or proxy routing is disabled. Do not fall back to local access.
- Inherit the first Skill's token-efficient stage contract. Preserve the source fingerprint, discovery union, image ledger, visual verdicts, family evidence, and sales as separate checkpoints; a failure in sales, report generation, or upload must not trigger another source-image analysis, Amazon search, image download, or verified visual pass.

## Workflow

### 1. Preserve and inspect the source

If the source is in a temporary path, copy it into the task output directory without modifying it. View it at original detail.

Determine whether it shows:

- one exact product;
- one product family with variants;
- multiple unrelated products;
- packaging plus the unboxed product;
- a specification table, dimension diagram, feature panels, or accessory list.

When one image presents a coherent product family, analyze the family by default and treat each printed model/variant as a sub-target. Ask the user only when unrelated products are present or the target choice would materially change the market.

### 2. Extract evidence without mixing fact and inference

Read [references/image-intake-schema.md](references/image-intake-schema.md) and create a source-fingerprint JSON.

Separate:

- **printed facts**: exact visible text such as brand, item number, model, dimensions, age, functions, battery, and pack quantity;
- **visual observations**: silhouette, mold, cab/body shape, mechanism, accessory layout, colors, and relative scale;
- **uncertain readings**: blurred, occluded, translated, or ambiguous text;
- **variants**: each model code and the visible difference from the common family.

Never promote a visual guess into a printed fact. Preserve the original spelling, then add normalized English search phrases separately.

### 3. Define the image-based target

Write two fingerprints:

1. **family fingerprint** — the common mold direction, mechanism, theme, pack format, and shared accessories;
2. **variant fingerprints** — the attachment, vehicle type, color, or included-piece changes for each printed model.

Identify mandatory Tier 1 traits. For a set, include both the hero product mold and the accessory/pack composition; do not judge only one loose piece.

### 4. Build the search ladder

Create independent Amazon US query families in this order:

1. exact identity: brand + model/item number;
2. exact series/product name + model;
3. distinctive printed phrase + toy type;
4. exact composition: hero product + mechanism + accessory set/count;
5. variant queries: one query family for each important model/attachment;
6. visual structure synonyms: body type, mold features, transformation, storage, carrier, folding, sound/light/inertia, or the applicable mechanism;
7. broad toy-node and SellerSprite sales audit with strong context terms.

Do not rely on a single model-number search: supplier model codes may be absent from Amazon listings. Do not use unrestricted ambiguous words such as `carrier`, `crew`, or `electric` without toy and structure context.

Use the first Skill's `scripts/vps_search_candidates.py` with `--seed-id` set to the exact SHA-256 identity supplied by the Runner for the preserved source image. Do not invent a label or reuse an identity from another image. Use 2–3 pages per query initially.

Apply the first Skill's depth-based market-audit range and coverage-evidence contract. A supplier image does not reduce the required SellerSprite sales-ranked audit; use the extracted structure and likely Amazon anchor to build the theme-neutral and adjacent-theme query paths.

Also inherit its family-variation expansion, exact ranked-review order, verified `localImagePath`, and raw-source union requirements. The absence of an Amazon seed does not relax those checks.

### 5. Look for an Amazon anchor, then keep searching

An anchor listing is useful when its image, mold, composition, and printed identity strongly match the source. Confirm it from the saved product image and detail data, not title alone.

- If an exact anchor exists, scrape its details and add its traffic relations and category nodes to the candidate paths.
- If several rebranded anchors exist, keep them all and group by parent/mold evidence.
- If no exact anchor exists, continue with the source fingerprint as the target; do not force the nearest Amazon product to become the seed.

Finding one exact listing does not end the task. Continue until the first Skill's coverage stopping rule is met.

### 6. Download candidate images and compare to the source

Use the first Skill's `scripts/vps_download_images.py`. Build contact sheets with the original source image in the first red-bordered cell.

For a variant-family source, add `matchedSourceVariant` to each decision. Use `family` only when the candidate matches common traits but no single variant can be identified.

Assign tiers as follows:

- **Tier 1 — 核心同款市场:** same or effectively identical hero-product mold, main mechanism, and pack composition; allow rebranding, packaging, language, and minor color changes. For a family source, matching any displayed variant can qualify if the variant is recorded.
- **Tier 2 — 扩展同款市场:** same mold family or unmistakable design direction, but vehicle attachment, variant, piece count, accessory set, or one material structure changes.
- **Tier 3 — 外围结构市场:** same physical playset concept and interaction, but the principal molds or pack architecture differ.
- **Excluded:** same theme, age, function, or need without a meaningful exterior relationship.

Title similarity alone cannot assign a tier. Sales never assign a tier.

### 7. Validate product families and sales

Use SellerSprite ASIN batches after visual judgment to fill price, rating, BSR, node, and supporting parent evidence. Then use the exact-month `asin_sales_trend` response for every selected ASIN: only `parentUnitSales`/`parentSalesRevenue` populate parent-family metrics, and only `childUnitSales` populates child sales. Group rebrands/variations when parent or unmistakable mold evidence supports it. Keep “same mold across unrelated sellers” as a visual family note unless a parent relationship is verified.

Never treat `competitor_lookup.totalUnits` as parent-family sales. Missing, null, failed, or ASIN-mismatched trends remain blank and are disclosed with the month and metric uncertainty.

### 8. Deliver the result

Provide:

1. the preserved source image and extracted fingerprint;
2. the query families and Amazon/SellerSprite coverage range;
3. Tier 1, Tier 2, and Tier 3 contact sheets;
4. ASIN, title, price, estimated units, matched source variant, and visual reason;
5. exact-anchor findings or an explicit “no exact anchor verified” statement;
6. high-sales products visually inspected but excluded;
7. parent-family and possible same-mold grouping warnings;
8. one concrete boundary question only when user judgment is genuinely needed.

Use “候选发现” or “覆盖检查” in Chinese output. Do not use the Chinese term “召回”. Do not claim reverse-image matching unless an actual reverse-image service was used; describe this workflow as image-feature extraction plus Amazon visual verification.
