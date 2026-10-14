# Output contract

## Candidate record

Keep these fields when available:

```json
{
  "asin": "B000000000",
  "parentAsin": "B000000001",
  "visualFamilyId": "VF-001",
  "title": "Product title",
  "brand": "Brand",
  "price": 29.99,
  "rating": 4.5,
  "reviews": 123,
  "units": 456,
  "parentUnits": 456,
  "childUnits": 120,
  "unitsScope": "parent",
  "salesMonth": "YYYYMM",
  "image": "internal source URL",
  "localImagePath": "absolute saved path",
  "sourceQueries": ["query one"],
  "sourceTypes": ["amazon-search", "sellersprite-node"],
  "tier": 1,
  "visualReason": "Concise evidence for the tier"
}
```

Do not expose `image` in user-facing output. Display `localImagePath` only.

## Decision file

Use this format with `scripts/compile_tiers.py`:

```json
{
  "seedAsin": "B000000000",
  "salesMonth": "YYYYMM",
  "decisions": [
    {
      "asin": "B000000002",
      "outcome": "tier_1",
      "imageReviewed": true,
      "visualReason": "Same shell, openings, and four-piece arrangement"
    },
    {
      "asin": "B000000004",
      "outcome": "excluded",
      "imageReviewed": true,
      "visualReason": "Same theme but flatbed silhouette"
    }
  ]
}
```

Allowed outcomes: `seed`, `screened_out`, `tier_1`, `tier_2`, `tier_3`, and `excluded`. The ASIN set in this file must equal the ASIN set in `outputs/candidate-manifest.json`. Tier outcomes must equal the ASIN set in the final product list.

Final product rows use `tier: "Tier 1"`, `"Tier 2"`, or `"Tier 3"`; the underscored values belong only to decision outcomes. The top-level result `dataMonth` uses `YYYY-MM`. SellerSprite tool requests use the compact `YYYYMM` form required by that API, but that request form must not leak into the final result.

## Sales and family fields

- `parentUnits`: SellerSprite parent-family monthly units, counted once for each normalized `parentAsin`.
- `childUnits`: exact child-ASIN monthly units from sales-trend evidence; null when unavailable.
- `units`: retained as a compatibility alias for the raw SellerSprite lookup value. Do not sum it across siblings.
- `unitsScope`: `parent`, `child`, or `unknown`.
- `visualFamilyId`: a stable task-local identifier for the same mold direction across one or more Amazon parents.
- `metricMonth` and `metricSource`: the month and SellerSprite method that produced the sales value.

SellerSprite may return fewer rows than requested. Preserve the product row, set unavailable sales fields to null, and list the ASIN in `sellerSpriteMissingAsins`.

## Final response order

1. One-sentence target visual definition.
2. Tier 1 contact sheet and top products.
3. Tier 2 contact sheet and boundary explanation.
4. Tier 3 contact sheet and context explanation.
5. High-sales exclusions.
6. Parent-family overlap warning.
7. Data month, source limitations, and one concrete user decision if needed.

Never claim “all competitors” without qualification. Say which search paths, pages, nodes, sales range, and stopping rule were used.
