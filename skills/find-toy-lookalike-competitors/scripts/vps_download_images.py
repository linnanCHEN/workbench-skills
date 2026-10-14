import argparse
import importlib.util
import json
import os
import sys
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


def write_checkpoint(source, downloaded, output, complete):
    payload = dict(source)
    payload["candidates"] = downloaded
    payload["downloadedCount"] = sum(
        bool(item.get("localImagePath")) for item in downloaded
    )
    payload["checkpointComplete"] = complete
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Download candidate images through the VPS")
    parser.add_argument("--input", required=True)
    parser.add_argument("--image-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--client")
    args = parser.parse_args()

    client = load_client(find_client(args.client))
    require_proxy_health(client)
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])
    image_dir = Path(args.image_dir).resolve()
    image_dir.mkdir(parents=True, exist_ok=True)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for index, product in enumerate(candidates, 1):
        asin = str(product.get("asin") or f"unknown-{index}")
        image_url = (
            product.get("normalizedImage")
            or product.get("image")
            or product.get("imageUrl")
            or product.get("sellerSpriteImage")
        )
        target = image_dir / f"{index:03d}-{asin}.jpg"
        if target.exists() and target.stat().st_size > 0:
            status = 200
            result = {"path": str(target), "bytes": target.stat().st_size, "resumed": True}
        elif not image_url:
            status = 422
            result = {"error": "missing_image_url"}
        else:
            status, result = client.download_image(image_url, target)

        copy = dict(product)
        copy["imageDownloadHttpStatus"] = status
        copy["localImagePath"] = result.get("path") if isinstance(result, dict) else None
        copy["imageDownloadError"] = (
            result.get("error") if isinstance(result, dict) and status >= 300 else None
        )
        downloaded.append(copy)
        write_checkpoint(data, downloaded, output, index == len(candidates))
        print(
            f"{index:03d}/{len(candidates):03d} {asin} http={status} "
            f"bytes={result.get('bytes') if isinstance(result, dict) else None}",
            flush=True,
        )

    write_checkpoint(data, downloaded, output, True)
    count = sum(bool(item.get("localImagePath")) for item in downloaded)
    print(f"saved={output} downloaded={count}")
    return 0 if count else 1


if __name__ == "__main__":
    raise SystemExit(main())

