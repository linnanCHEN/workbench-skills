# Coverage evidence

Use this contract for `outputs/candidate-manifest.json`. It lets the Runner distinguish a complete, auditable search from a self-consistent but incomplete shortlist.

```json
{
  "schemaVersion": 2,
  "seedAsin": "B000000000",
  "audit": {
    "scanTarget": 200,
    "reviewTarget": 50,
    "reviewAsins": ["B000000001"],
    "queryFamilies": ["exact structure", "theme-neutral structure"],
    "shortfallReason": null,
    "stoppingEvidence": [
      {"queryFamily": "new synonym one", "newTier1Families": 0},
      {"queryFamily": "new synonym two", "newTier1Families": 0}
    ]
  },
  "candidates": [
    {
      "asin": "B000000001",
      "title": "Product title",
      "sourceTypes": ["sellersprite-high-sales"],
      "sourceQueries": ["theme-neutral structure"]
    }
  ]
}
```

## Invariants

- `scanTarget` and `reviewTarget` must match the task depth supplied by the Runner.
- `reviewAsins` starts with the first `reviewTarget` distinct ASINs actually returned by valid sales-ranked discovery calls. Those early ranked rows cannot be title-screened. If the sources return fewer, exhaust every ranked path, review all returned ASINs, and explain the evidenced shortfall in `shortfallReason`.
- Valid SellerSprite ranked calls start on page 1, use consecutive pages, `variation=N`, descending `total_units`, and `returnFields="asin,title,units,imageUrl,parent"`. A keyword path uses `matchType=1`, or `keywordEqual=true` for an intentionally exact query; a keyword-free path uses a specific relevant toy `nodeIdPath`. Use `keyword`, not `keywords`, for `product_research`. The `units` projection preserves the current MCP's numeric monthly volume; `totalUnits` may be returned as null. Their request page and size must agree with the response. A path is exhausted only when response pagination proves a terminal page through `hasNextPage:false`, an explicit terminal flag, `page >= pages`, or a consistent `total/page/size` calculation; deduplicated row count alone is never terminal proof. Contradictory pagination invalidates the path. A blank response `order.field` echo alone does not invalidate a request that asked for descending `total_units`. Rank the combined distinct rows globally by numeric `units` or legacy `totalUnits` descending, with nulls last and stable API order for ties.
- `queryFamilies` records distinct discovery ideas, not page numbers or spelling-only duplicates.
- `stoppingEvidence` contains the exact final two VPS Amazon query strings, in execution order. Both must report zero newly discovered Tier 1 visual families against the discovery state that existed before those probe calls; later detail, image-source, or variation enrichment must not make the probe look older than it was.
- A non-Amazon coverage repair reuses the already valid Amazon artifact and command evidence without rerunning the search. If Amazon evidence itself must be repaired, the pass reruns the prior query strings in the same order and never invents new wording, because doing so expands the cross-attempt source union and invalidates the meaning of the earlier stopping probes. A Runner-supplied repair scaffold preserves all prior candidates and may auto-fill only non-mandatory `screened_out` decisions; every mandatory image decision still requires a verified image artifact. A Runner-prefilled `image-review-candidates.json` is authoritative for all currently resolvable required and previously reviewed images: preserve every row and exact URL, append only unresolved exact-ASIN results, and never shrink it back to an older image list. A non-family repair also reuses the verified family artifact and makes no new `asin_detail` calls. When family repair is genuinely required, query only the exact representative ASINs listed by the contract and never add a returned parent as an extra lookup.
- The candidate list is exactly the union of the raw Amazon search file, `outputs/family-variation-candidates.json`, every ASIN returned by SellerSprite discovery calls, the seed, and any operator-supplied audit ASINs.
- SellerSprite traffic ASINs, expanded family variations, `reviewAsins`, and operator-audit ASINs require downloaded-image review. They cannot be title-screened.
- Every `imageReviewed: true` candidate stores its verified downloaded path in `localImagePath`; it must match the digest-bearing `outputs/image-download-ledger.json`, resolve under `outputs/images`, include the ASIN in its filename, and contain a valid JPG, PNG, or WebP of at least 64×64 pixels whose extension and recorded `contentType` agree with its bytes. Its ledger `sourceImageUrl` must exactly match a URL observed for the same ASIN in the verified VPS inventory or a successful, marketplace/month/request-bound SellerSprite response.
- Parent ASIN is grouping evidence only. Keep all discovered child ASINs in the candidate and decision ledgers.
- `outputs/family-variation-candidates.json` uses schema version 1 and contains one successful `asin_detail` query record per selected parent or verified singleton family. Each query's `children` must exactly equal the complete returned `variationList`; its candidate ledger is their exact union.
- Every selected child ASIN must be present in its representative's verified `variationList`, and its final `parentAsin` must exactly match the parent recorded for that child. A verified `parentAsin: null` is an authoritative singleton, not a missing value.
- A source conflict, including two different parents for the same child across sources or months, must be recorded for review rather than silently overwritten. Conflicting parent-level sales must remain blank until reconciled.

The task may contain more candidates than the review cohort. Candidates outside the mandatory cohort may use `screened_out` only with a concrete structured reason. Never use a numeric score, page boundary, or batch size as that reason.
