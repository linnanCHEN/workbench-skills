# VPS API reference

## Authentication

The public client requires an explicit HTTPS base URL and token. HTTP URLs,
including loopback, are rejected. Private SSH profiles are not used.
Set the token in the process environment:

```text
AMAZON_SCRAPER_VPS_TOKEN=<secret>
```

Requests use:

```http
Authorization: Bearer <secret>
```

Never put the token in a URL, source file, output, or chat response.

## Health

```http
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "proxy_configured": true,
  "active_job": false
}
```

Do not submit a scrape when `proxy_configured` is false.

## Scrape

```http
POST /scrape
Content-Type: application/json
Authorization: Bearer <secret>

{
  "url": "https://www.amazon.com/s?k=toy",
  "pages": 2
}
```

The service accepts HTTPS URLs on `amazon.com` or its subdomains. Pages are
limited to 1–5. Only one job runs at a time.

## Secure image download

```http
POST /image
Content-Type: application/json
Authorization: Bearer <secret>

{
  "url": "https://m.media-amazon.com/images/I/example.jpg"
}
```

The response is the image bytes. This endpoint accepts only HTTPS URLs on
Amazon image CDN domains, follows no redirects outside that allowlist, and
always uses a configured proxy. It fails closed when no proxy is available.

The bundled client saves the bytes to a local file without exposing the token:

```powershell
python scripts/call_vps.py image "<amazon-image-url>" --output "<local-file>"
```

## Status codes

- `200`: health check, scrape, or image download completed.
- `400`: invalid Amazon page or image URL.
- `401`: missing or incorrect API token.
- `413`: request body too large.
- `429`: another scrape is running.
- `502`: browser or extraction failure.
- `503`: proxy is not configured; direct access is disabled.

## Data interpretation

- `boughtPastMonth` is display text such as `1K+`; it is not exact sales.
- Search results may contain sponsored listings.
- BSR and search ordering are different datasets.
- Selectors can break after Amazon changes its page structure.

## Client failure contract

Paths above are relative to the configured base URL. `request()` and `download_image()`
retain `(http_status, result_dict)` for service and business outcomes. Missing or invalid
API configuration raises `RuntimeError` before credential lookup or network access;
the CLI converts this into a fixed error and exit code 1. HTTP failures, proxy-disabled
health, blocked/failed scraping, empty results, and invalid images return non-success.
CLI exits 1 on failure, including HTTP 200 with unsuccessful business status.
Errors use fixed categories; credentials and service error bodies are not exposed.
The client validates Amazon US targets, checks proxy readiness, rejects redirects,
and checks image size, MIME type and signature before replacing an output file.
