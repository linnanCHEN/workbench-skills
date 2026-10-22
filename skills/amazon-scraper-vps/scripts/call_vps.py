"""Call an explicitly configured HTTPS VPS API without private transport profiles."""
import argparse
import base64
import ctypes
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path
from typing import Any

CREDENTIAL_TARGET = "Codex/AmazonScraperVPS"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024


class CREDENTIALW(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD), ("Attributes", wintypes.LPVOID),
                ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR)]


def read_windows_credential() -> str:
    if os.name != "nt":
        return ""
    pointer = ctypes.POINTER(CREDENTIALW)()
    api = ctypes.WinDLL("Advapi32.dll")
    api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            ctypes.POINTER(ctypes.POINTER(CREDENTIALW))]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [wintypes.LPVOID]
    if not api.CredReadW(CREDENTIAL_TARGET, 1, 0, ctypes.byref(pointer)):
        return ""
    try:
        item = pointer.contents
        if not item.CredentialBlob or not item.CredentialBlobSize:
            return ""
        return ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize).decode("utf-16-le").strip()
    finally:
        api.CredFree(pointer)


def validate_base_url(value: str) -> str:
    url = urllib.parse.urlsplit(value)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment or any(ord(char) < 33 for char in value)):
        raise RuntimeError("AMAZON_SCRAPER_VPS_URL must be an HTTPS base URL without credentials, query, or fragment")
    return value.rstrip("/")


def api_credentials(require_token: bool = False) -> tuple[str, str]:
    value = os.environ.get("AMAZON_SCRAPER_VPS_URL", "").strip()
    if not value:
        raise RuntimeError("AMAZON_SCRAPER_VPS_URL is required")
    # Validate the explicit public endpoint before accessing any saved credential.
    base_url = validate_base_url(value)
    token = os.environ.get("AMAZON_SCRAPER_VPS_TOKEN", "").strip() or read_windows_credential()
    if require_token and not token:
        raise RuntimeError("AMAZON_SCRAPER_VPS_TOKEN is required")
    return base_url, token


def validate_operation(path: str, method: str, payload: Any) -> None:
    if path == "/health" and method == "GET" and payload is None:
        return
    if path not in {"/scrape", "/image"} or method != "POST" or not isinstance(payload, dict):
        raise ValueError("invalid_request")
    value = payload.get("url")
    if not isinstance(value, str) or len(value) > 8192 or any(ord(char) < 33 for char in value):
        raise ValueError("invalid_target_url")
    url = urllib.parse.urlsplit(value)
    if url.scheme != "https" or url.username or url.password or url.port not in {None, 443}:
        raise ValueError("invalid_target_url")
    domains = ("amazon.com",) if path == "/scrape" else ("media-amazon.com", "ssl-images-amazon.com", "images-amazon.com", "images.amazon.com")
    if not any(url.hostname == domain or (url.hostname or "").endswith("." + domain) for domain in domains):
        raise ValueError("invalid_target_url")
    if path == "/scrape":
        pages = payload.get("pages", 1)
        if isinstance(pages, bool) or not isinstance(pages, int) or not 1 <= pages <= 5 or set(payload) - {"url", "pages"}:
            raise ValueError("invalid_pages")
    elif set(payload) != {"url"}:
        raise ValueError("invalid_request")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def valid_image(raw: bytes, content_type: str) -> bool:
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        return False
    signatures = {
        "image/jpeg": raw.startswith(b"\xff\xd8\xff"),
        "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP",
    }
    return signatures.get(content_type, False)


def http_call(base: str, token: str, path: str, method: str, payload: Any) -> tuple[int, dict]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"accept": "image/*" if path == "/image" else "application/json"}
    if body is not None:
        headers["content-type"] = "application/json"
    if token:
        headers["authorization"] = f"Bearer {token}"
    handlers = [NoRedirect()]
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with opener.open(req, timeout=260 if path == "/scrape" else 90) as response:
            limit = MAX_IMAGE_BYTES if path == "/image" else MAX_JSON_BYTES
            raw = response.read(limit + 1)
            if len(raw) > limit:
                return 502, {"error": "response_too_large"}
            if path == "/image":
                content_type = response.headers.get_content_type().lower()
                if not valid_image(raw, content_type):
                    return 502, {"error": "unexpected_image_response"}
                return response.status, {"image_base64": base64.b64encode(raw).decode("ascii"), "content_type": content_type}
            result = json.loads(raw)
            if not isinstance(result, dict):
                return 502, {"error": "invalid_json_response"}
            return response.status, result
    except urllib.error.HTTPError as error:
        return error.code, {"error": "http_error", "http_status": error.code}
    except (OSError, ValueError, urllib.error.URLError):
        return 502, {"error": "api_request_failed"}


def successful(path: str, status: int, result: dict) -> bool:
    if not 200 <= status < 300 or result.get("error"):
        return False
    if path == "/health":
        return result.get("status") == "ok" and result.get("proxy_configured") is True
    if path == "/scrape":
        return result.get("status") == "SUCCESS" and isinstance(result.get("products"), list) and bool(result["products"])
    return bool(result.get("image_base64")) or result.get("status") == "saved"


def perform(base: str, token: str, path: str, method: str, payload: Any) -> tuple[int, dict]:
    if path != "/health":
        status, result = http_call(base, token, "/health", "GET", None)
        if not successful("/health", status, result):
            return status if status >= 400 else 503, {"error": "vps_not_ready"}
    status, result = http_call(base, token, path, method, payload)
    if not successful(path, status, result):
        # Error bodies may contain proxy credentials or private URLs.
        return status if status >= 400 else 502, {"error": "vps_operation_failed", "http_status": status}
    return status, result


def request(path: str, method: str = "GET", payload: Any = None) -> tuple[int, dict]:
    try:
        validate_operation(path, method, payload)
        base, token = api_credentials(require_token=path != "/health")
        return perform(base, token, path, method, payload)
    except (OSError, ValueError):
        return 400, {"error": "invalid_configuration_or_request"}


def download_image(url: str, output: str | Path) -> tuple[int, dict]:
    status, result = request("/image", method="POST", payload={"url": url})
    if not successful("/image", status, result):
        return status, result
    temporary = None
    try:
        raw = base64.b64decode(result["image_base64"], validate=True)
        content_type = result.get("content_type", "")
        if not isinstance(content_type, str) or not valid_image(raw, content_type):
            raise ValueError("invalid_image_response")
        target = Path(output).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".part")
        temporary.write_bytes(raw)
        os.replace(temporary, target)
        return status, {"status": "saved", "path": str(target), "content_type": content_type, "bytes": len(raw)}
    except (OSError, ValueError, KeyError):
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        return 502, {"error": "image_save_failed"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Call an explicitly configured Amazon Scraper VPS")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("health")
    scrape = commands.add_parser("scrape")
    scrape.add_argument("url")
    scrape.add_argument("--pages", type=int, default=1)
    image = commands.add_parser("image")
    image.add_argument("url")
    image.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "health":
            status, result = request("/health")
        elif args.command == "scrape":
            status, result = request("/scrape", "POST", {"url": args.url, "pages": args.pages})
        else:
            status, result = download_image(args.url, args.output)
    except RuntimeError:
        status, result = 400, {"error": "invalid_configuration"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if successful("/" + args.command, status, result) else 1


if __name__ == "__main__":
    sys.exit(main())
