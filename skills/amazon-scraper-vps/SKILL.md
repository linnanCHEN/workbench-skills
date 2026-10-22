---
name: amazon-scraper-vps
description: Run authenticated Amazon product, search, BSR, new-release, and movers-and-shakers scraping through a continuously running VPS service with mandatory proxy routing. Use when the user asks to scrape Amazon in the cloud/VPS, avoid local execution or local IP access, schedule repeated Amazon collection, inspect VPS scraper health, or retrieve Amazon fields such as ASIN, title, price, rating, reviews, BSR, bought-past-month, images, bullets, and product details.
---

# Amazon Scraper VPS

Use the VPS API for Amazon collection. Do not run the original local
`amazon-scraper` Docker workflow when this skill is selected.

## Safety contract

- Send Amazon requests only through the VPS API.
- Require an API token from `AMAZON_SCRAPER_VPS_TOKEN` or the encrypted
  Windows Credential Manager entry `Codex/AmazonScraperVPS`.
- Never print the API token or persist it in a plaintext file.
- Refuse direct Amazon access when the VPS reports `proxy_configured: false`.
- Accept only HTTPS Amazon URLs.
- Never render Amazon CDN image URLs directly to the user. Download them with
  the authenticated VPS `/image` endpoint and display only the saved local file.
- Do not log proxy credentials, API tokens, cookies, or user passwords.
- Stop and report `blocked` or `scrape_failed`; do not solve or bypass CAPTCHAs.
- Treat `boughtPastMonth` as Amazon's displayed estimate, not verified sales.
- Treat keyword-search results as search ranking, not official BSR ranking.

## Inputs, outputs, and endpoint

Input: an authorized HTTPS Amazon US page URL (1–5 pages) or Amazon CDN image URL.
Output: an HTTP-style status and JSON result; images return `status: saved`, local
`path`, `content_type`, and `bytes`. Missing data is never invented. Upstream HTTP
errors retain their status; invalid local requests and unsuccessful business results
use non-success statuses.
Not for account changes, ads, CAPTCHA solving, local scraping, or competitor decisions.

Configure your own authenticated HTTPS VPS base URL with
`AMAZON_SCRAPER_VPS_URL`, for example `https://scraper.example.com/amazon-scraper`.
The public package has no default service address. Missing or invalid configuration
fails before any request. Configure `AMAZON_SCRAPER_VPS_TOKEN` separately; never
put credentials in the URL. No service access or account authorization is included.
The public client uses only an explicitly configured HTTPS API. It does not read
private SSH profiles, use SSH transport, or allow loopback HTTP as an exception.
Missing or invalid configuration stops before credential lookup or network access.

## Workflow

1. Run the health check:

```powershell
python scripts/call_vps.py health
```

2. Confirm both conditions:

```json
{"status":"ok","proxy_configured":true}
```

3. Choose the correct Amazon URL:

- Product detail: `https://www.amazon.com/dp/ASIN`
- Search: `https://www.amazon.com/s?k=keyword`
- BSR: `https://www.amazon.com/gp/bestsellers/category`
- New releases: `https://www.amazon.com/zg/new-releases/category`
- Movers: `https://www.amazon.com/zg/movers-and-shakers/category`

4. Submit the scrape:

```powershell
python scripts/call_vps.py scrape "https://www.amazon.com/dp/B001TQ6IHS"
```

For search pagination, pass `--pages 2`; the service caps it at 5.

5. Validate the returned JSON before analysis:

- Require `status: SUCCESS`.
- Check `totalProducts` and non-empty `products`.
- Report null or missing fields instead of inventing values.
- Deduplicate products by ASIN.

6. When images must be inspected or shown, save each image through the VPS:

```powershell
python scripts/call_vps.py image "https://m.media-amazon.com/images/I/example.jpg" --output "outputs/example.jpg"
```

Confirm the response says `status: saved`, then inspect and display the local
file. Do not open or embed the source Amazon image URL in a browser or message.

Read [references/api.md](references/api.md) for the request and response
contract or troubleshooting status codes. Regression cases are in
[golden-set](references/golden-set.md); run `python -B -m unittest discover -s tests`.

## Deployment asset

`assets/service/` contains the independent VPS Docker service. It is separate
from the original `amazon-scraper` Skill. Keep proxy credentials in the VPS
environment only; `assets/service/config/proxies.json` must remain empty.
