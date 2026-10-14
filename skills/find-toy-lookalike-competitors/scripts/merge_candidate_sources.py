import argparse
import json
import re
from pathlib import Path


LIST_FIELDS = ("sourceQueries", "sourceSellerSprite", "sourceTypes")
SELLER_FIELDS = {
    "units",
    "revenue",
    "bsr",
    "nodeId",
    "nodeIdPath",
    "nodeLabelPath",
    "parent",
    "parentAsin",
    "brand",
    "ratings",
}


def extract_items(payload):
    if isinstance(payload.get("candidates"), list):
        return payload["candidates"]
    if isinstance(payload.get("items"), list):
        return payload["items"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    raise ValueError("Input must contain candidates, items, or data.items")


def normalized_image(url):
    return re.sub(
        r"\._[^.]+_(?=\.[A-Za-z]{3,4}(?:\?|$))", "", str(url or "")
    )


def merge_item(current, item, source):
    if source not in current["sourceTypes"]:
        current["sourceTypes"].append(source)
    for key, value in item.items():
        if value in (None, "", [], {}):
            continue
        if key in LIST_FIELDS:
            existing = current.setdefault(key, [])
            for entry in value:
                if entry not in existing:
                    existing.append(entry)
        elif key == "imageUrl":
            current.setdefault("sellerSpriteImage", value)
            current.setdefault("image", value)
        elif key == "image":
            current["image"] = value
        elif key in SELLER_FIELDS or key not in current:
            current[key] = value


def main():
    parser = argparse.ArgumentParser(description="Merge candidate JSON files by ASIN")
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed-asin")
    args = parser.parse_args()

    merged = {}
    for input_name in args.input:
        path = Path(input_name).resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        source = path.stem
        for item in extract_items(payload):
            asin = str(item.get("asin") or "").strip().upper()
            if not asin:
                continue
            current = merged.setdefault(asin, {"asin": asin, "sourceTypes": []})
            merge_item(current, item, source)

    candidates = []
    for item in merged.values():
        image = item.get("image") or item.get("sellerSpriteImage")
        if image:
            item["normalizedImage"] = normalized_image(image)
        candidates.append(item)
    candidates.sort(
        key=lambda item: (
            item.get("units") is not None,
            item.get("units") or -1,
            len(item.get("sourceTypes") or []),
        ),
        reverse=True,
    )
    output_payload = {
        "seedAsin": (args.seed_asin or "").upper() or None,
        "candidateCount": len(candidates),
        "candidates": candidates,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved={output} candidates={len(candidates)}")


if __name__ == "__main__":
    main()

