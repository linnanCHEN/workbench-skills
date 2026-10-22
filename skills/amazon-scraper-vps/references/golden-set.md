# Public API regression cases

- An explicit HTTPS API URL is required; missing configuration, HTTP including
  loopback, credentials in the URL, query strings, and fragments fail closed.
- Invalid configuration stops before stored credential lookup or network access.
- Private SSH profiles cannot override or replace explicit HTTPS API configuration.
- Non-Amazon targets, extra fields, and invalid page counts fail before requests.
- Disabled proxy prevents business requests; HTTP 401 and HTTP 200 FAILED/empty
  product responses remain failures without exposing private error bodies.
- Redirects are rejected; image size, MIME type, and JPEG/PNG/WebP signatures are checked.
- A successful image preserves saved path/bytes and atomic writing; invalid images
  never replace an existing file. Full image decoding belongs to live acceptance.
- Parent link/image Skills retain `request()` and `download_image()` contracts.
- CLI configuration and business failures return a safe message and nonzero exit.

Run `python -B -m unittest discover -s tests`. The original public-configuration
tests remain unchanged. Live service/proxy/Amazon acceptance is separate.
