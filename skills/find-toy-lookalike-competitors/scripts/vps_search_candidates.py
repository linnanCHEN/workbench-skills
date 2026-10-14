import argparse
import importlib.util
import json
import os
import sys
import urllib.parse
from pathlib import Path


def find_client(explicit=None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(
        Path(__file__).resolve().parents[2]
        / "amazon-scraper-vps"
        / "scripts"
        / "call_vps.py"
    )
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(
            Path(codex_home) / "skills" / "amazon-scraper-vps" / "scripts" / "call_vps.py"
        )
    candidates.append(
        Path.home() / ".codex" / "skills" / "amazon-scraper-vps" / "scripts" / "call_vps.py"
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "amazon-scraper-vps/scripts/call_vps.py not found; install that skill or pass --client"
    )


def load_client(path):
    spec = importlib.util.spec_from_file_location("amazon_vps_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_proxy_health(client):
    status, result = client.request("/health")
    if not (
        200 <= status < 300
        and result.get("status") == "ok"
        and result.get("proxy_configured") is True
    ):
        raise RuntimeError(f"VPS proxy health check failed: http={status} result={result}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Search Amazon US through amazon-scraper-vps and merge results by ASIN"
    )
    seed = parser.add_mutually_exclusive_group(required=True)
    seed.add_argument("--seed-asin")
    seed.add_argument("--seed-id")
    parser.add_argument("--query", action="append", dest="queries", required=True)
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--output", required=True)
    parser.add_argument("--client")
    args = parser.parse_args()

    client = load_client(find_client(args.client))
    require_proxy_health(client)
    per_query = []
    candidates = {}
    pages = max(1, min(5, args.pages))
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    def write_checkpoint(complete):
        payload = {
            "seedAsin": args.seed_asin.upper() if args.seed_asin else None,
            "seedId": args.seed_id if args.seed_id else None,
            "marketplace": "US",
            "pagesPerQuery": pages,
            "checkpointComplete": complete,
            "queries": per_query,
            "uniqueCandidates": len(candidates),
            "candidates": list(candidates.values()),
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    for query in args.queries:
        url = f"https://www.amazon.com/s?k={urllib.parse.quote_plus(query)}"
        status, result = client.request(
            "/scrape", method="POST", payload={"url": url, "pages": pages}
        )
        result_status = result.get("status") if isinstance(result, dict) else None
        products = result.get("products", []) if isinstance(result, dict) else []
        valid = 200 <= status < 300 and result_status == "SUCCESS"
        per_query.append(
            {
                "query": query,
                "httpStatus": status,
                "resultStatus": result_status,
                "products": len(products) if valid else 0,
            }
        )
        print(
            f"query={query!r} http={status} status={result_status} products={len(products)}",
            flush=True,
        )
        if not valid:
            write_checkpoint(False)
            continue
        for product in products:
            asin = str(product.get("asin") or "").strip().upper()
            if not asin:
                continue
            current = candidates.setdefault(asin, dict(product))
            current["asin"] = asin
            current.setdefault("sourceQueries", [])
            if query not in current["sourceQueries"]:
                current["sourceQueries"].append(query)
        write_checkpoint(False)

    write_checkpoint(True)
    print(f"saved={output} uniqueCandidates={len(candidates)}", flush=True)
    return 0 if candidates else 1


if __name__ == "__main__":
    raise SystemExit(main())
