import argparse
import ctypes
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path


CREDENTIAL_TARGET = "Codex/AmazonScraperVPS"
MAX_IMAGE_BYTES = 12 * 1024 * 1024


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", wintypes.LPVOID),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def read_windows_credential():
    if os.name != "nt":
        return ""
    credential_pointer = ctypes.POINTER(CREDENTIALW)()
    advapi32 = ctypes.WinDLL("Advapi32.dll")
    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(CREDENTIALW)),
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [wintypes.LPVOID]
    if not advapi32.CredReadW(
        CREDENTIAL_TARGET, 1, 0, ctypes.byref(credential_pointer)
    ):
        return ""
    try:
        credential = credential_pointer.contents
        if not credential.CredentialBlob or not credential.CredentialBlobSize:
            return ""
        raw = ctypes.string_at(
            credential.CredentialBlob, credential.CredentialBlobSize
        )
        return raw.decode("utf-16-le").strip()
    finally:
        advapi32.CredFree(credential_pointer)


def api_credentials(require_token: bool = False) -> tuple[str, str]:
    base_url = os.environ.get("AMAZON_SCRAPER_VPS_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("AMAZON_SCRAPER_VPS_URL is required")
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment):
        raise RuntimeError("AMAZON_SCRAPER_VPS_URL must be an HTTPS base URL without credentials, query or fragment")
    token = os.environ.get("AMAZON_SCRAPER_VPS_TOKEN", "").strip()
    if not token:
        token = read_windows_credential()
    if require_token and not token:
        raise RuntimeError("AMAZON_SCRAPER_VPS_TOKEN is required")
    return base_url, token


def request(path, method="GET", payload=None):
    base_url, token = api_credentials(require_token=path in {"/scrape", "/image"})

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"accept": "application/json"}
    if body is not None:
        headers["content-type"] = "application/json"
    if token:
        headers["authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=260) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            result = json.load(error)
        except Exception:
            result = {"error": "http_error", "message": str(error)}
        return error.code, result


def download_image(url, output):
    base_url, token = api_credentials(require_token=True)
    body = json.dumps({"url": url}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/image",
        data=body,
        headers={
            "accept": "image/*",
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            content_type = response.headers.get_content_type().lower()
            if not content_type.startswith("image/"):
                return 502, {"error": "unexpected_content_type"}
            declared = int(response.headers.get("content-length", "0") or "0")
            if declared > MAX_IMAGE_BYTES:
                return 502, {"error": "image_too_large"}

            target = Path(output).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f"{target.name}.part")
            size = 0
            try:
                with temporary.open("wb") as handle:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_IMAGE_BYTES:
                            raise RuntimeError("image_too_large")
                        handle.write(chunk)
                os.replace(temporary, target)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
            return response.status, {
                "status": "saved",
                "path": str(target),
                "content_type": content_type,
                "bytes": size,
            }
    except urllib.error.HTTPError as error:
        try:
            result = json.load(error)
        except Exception:
            result = {"error": "http_error", "message": str(error)}
        return error.code, result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Call the Amazon Scraper VPS")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("health")
    scrape = subcommands.add_parser("scrape")
    scrape.add_argument("url")
    scrape.add_argument("--pages", type=int, default=1)
    image = subcommands.add_parser("image")
    image.add_argument("url")
    image.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.command == "health":
        status, result = request("/health")
    elif args.command == "scrape":
        status, result = request(
            "/scrape",
            method="POST",
            payload={"url": args.url, "pages": max(1, min(5, args.pages))},
        )
    else:
        status, result = download_image(args.url, args.output)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
