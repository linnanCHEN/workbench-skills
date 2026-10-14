# Image intake schema

Create this record before Amazon searching:

```json
{
  "sourceId": "IMAGE-STABLE-ID",
  "sourceImagePath": "absolute local path",
  "analysisUnit": "single-product | variant-family | multiple-products",
  "printedFacts": {
    "brand": null,
    "series": null,
    "productName": null,
    "modelNumbers": [],
    "age": null,
    "packageDimensions": null,
    "productDimensions": null,
    "functions": [],
    "battery": null,
    "packQuantity": null,
    "otherText": []
  },
  "visualObservations": {
    "toyType": null,
    "primarySilhouette": null,
    "mainStructure": null,
    "mechanism": [],
    "pieceArrangement": null,
    "sharedAccessories": [],
    "colorTheme": null,
    "scaleRelationships": null
  },
  "variants": [
    {
      "code": "MODEL-A",
      "visibleDifference": "Attachment or vehicle difference",
      "confidence": "high | medium | low"
    }
  ],
  "uncertainReadings": [],
  "mandatoryTier1Traits": [],
  "normalizedSearchConcepts": [],
  "queryFamilies": []
}
```

## Evidence rules

- Copy printed text exactly before normalizing it.
- Use `null` for absent fields.
- Put unclear characters in `uncertainReadings`; do not silently correct them.
- Describe only visible variant differences. Do not name a vehicle or accessory when the image is too small to distinguish it.
- Treat package and product dimensions as separate facts.
- Do not infer sales, material, certification, battery type, or age from visual appearance.

## Fictional information-image example

This invented example demonstrates the record structure only. It does not describe a supplied image, real supplier, or verified product. Assume a fictional image clearly prints these facts:

- brand: `EXAMPLE TOYS`;
- series mark: `EXAMPLE BUILDERS` / `MOTION PLAY`;
- product name: `EXAMPLE LIGHT & SOUND TRUCK SET`;
- item numbers: `DEMO100A/B/C/D`;
- package size: `24X16X12CM`;
- functions: lighting, sound, inertia, battery powered;
- battery text: `AG13X3`;
- four displayed variants sharing a construction-site accessory family.

Assume the fictional image also visually shows yellow construction vehicles, workers, signs, barriers, a crane, road pieces, and a small building. The exact identity of every small vehicle should remain a visual observation unless inspected at sufficient resolution.

## Query derivation example

For this fictional example, derive independent searches such as:

- `Example Toys DEMO100`;
- `Example Builders DEMO100 construction toy`;
- `sound light inertia construction truck playset`;
- `construction vehicle playset crane workers road signs sound light`;
- variant-specific vehicle queries after each vehicle is confidently identified.

Keep exact-identity queries separate from structural queries so a missing supplier model number does not hide rebranded Amazon listings.

