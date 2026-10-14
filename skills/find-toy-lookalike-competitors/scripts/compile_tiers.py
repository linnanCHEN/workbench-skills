import argparse
import json
from collections import defaultdict
from pathlib import Path


ALLOWED = {"1", "2", "3", "excluded"}


def normalize_tier(value):
    tier = str(value).lower().replace("tier", "").strip(" -_")
    if tier not in ALLOWED:
        raise ValueError(f"Unsupported tier {value!r}; use 1, 2, 3, or excluded")
    return tier


def main():
    parser = argparse.ArgumentParser(description="Apply visual decisions to candidate records")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    candidate_data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    decision_data = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    by_asin = {
        str(item.get("asin") or "").upper(): item
        for item in candidate_data.get("candidates", [])
        if item.get("asin")
    }
    groups = {key: [] for key in ALLOWED}
    missing = []

    for decision in decision_data.get("decisions", []):
        asin = str(decision.get("asin") or "").upper()
        if not asin:
            continue
        if asin not in by_asin:
            missing.append(asin)
            continue
        tier = normalize_tier(decision.get("tier"))
        item = dict(by_asin[asin])
        item.update({key: value for key, value in decision.items() if value is not None})
        item["asin"] = asin
        item["tier"] = tier
        item["salesMonth"] = decision.get("salesMonth") or decision_data.get("salesMonth")
        groups[tier].append(item)

    for items in groups.values():
        items.sort(
            key=lambda item: (
                item.get("units") is not None,
                item.get("units") or -1,
            ),
            reverse=True,
        )

    family_tiers = defaultdict(set)
    family_members = defaultdict(list)
    for tier, items in groups.items():
        if tier == "excluded":
            continue
        for item in items:
            family = str(item.get("parentAsin") or item.get("parent") or item["asin"])
            family_tiers[family].add(tier)
            family_members[family].append(item["asin"])
    overlaps = [
        {
            "family": family,
            "tiers": sorted(tiers),
            "asins": sorted(family_members[family]),
        }
        for family, tiers in family_tiers.items()
        if len(tiers) > 1
    ]

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    explicit_seed_id = decision_data.get("seedId")
    seed_asin = decision_data.get("seedAsin")
    if not seed_asin and not explicit_seed_id:
        seed_asin = candidate_data.get("seedAsin")
    seed_id = explicit_seed_id or candidate_data.get("seedId")
    for tier in ("1", "2", "3", "excluded"):
        payload = {
            "seedAsin": seed_asin,
            "seedId": seed_id,
            "salesMonth": decision_data.get("salesMonth"),
            "tier": tier,
            "count": len(groups[tier]),
            "candidates": groups[tier],
        }
        (output_dir / f"tier-{tier}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    summary = {
        "seedAsin": seed_asin,
        "seedId": seed_id,
        "salesMonth": decision_data.get("salesMonth"),
        "counts": {tier: len(items) for tier, items in groups.items()},
        "familyCounts": {
            tier: len(
                {
                    str(item.get("parentAsin") or item.get("parent") or item["asin"])
                    for item in items
                }
            )
            for tier, items in groups.items()
        },
        "crossTierFamilyOverlaps": overlaps,
        "missingDecisionAsins": missing,
    }
    summary_path = output_dir / "tier-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"saved={summary_path}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
