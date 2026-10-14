const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { request: playwrightRequest } = require('playwright');

const PORT = Number.parseInt(process.env.PORT || '8790', 10);
const API_TOKEN = String(process.env.EXTRACTOR_API_TOKEN || '').trim();
const MAX_BODY_BYTES = 16 * 1024;
const MAX_RESULT_BYTES = 20 * 1024 * 1024;
const MAX_IMAGE_BYTES = 12 * 1024 * 1024;
const JOB_TIMEOUT_MS = 240_000;
const IMAGE_TIMEOUT_MS = 60_000;
let activeJob = false;

function json(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(payload),
    'cache-control': 'no-store',
  });
  res.end(payload);
}

function authorized(req) {
  if (!API_TOKEN) return false;
  const supplied = String(req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  const left = Buffer.from(supplied);
  const right = Buffer.from(API_TOKEN);
  return left.length === right.length && crypto.timingSafeEqual(left, right);
}

function validAmazonUrl(value) {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    if (url.protocol !== 'https:') return null;
    if (host !== 'amazon.com' && !host.endsWith('.amazon.com')) return null;
    return url.href;
  } catch {
    return null;
  }
}

function hostMatches(host, base) {
  return host === base || host.endsWith(`.${base}`);
}

function validAmazonImageUrl(value) {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    if (url.protocol !== 'https:') return null;
    const allowed = [
      'media-amazon.com',
      'ssl-images-amazon.com',
      'images-amazon.com',
    ].some((base) => hostMatches(host, base)) || host === 'images.amazon.com';
    return allowed ? url.href : null;
  } catch {
    return null;
  }
}

function loadProxyUrls() {
  const multi = String(process.env.AMAZON_PROXIES || '').trim();
  if (multi) return multi.split(',').map((item) => item.trim()).filter(Boolean);
  const single = String(process.env.AMAZON_PROXY || '').trim();
  if (single) return [single];
  try {
    const configPath = path.join(__dirname, 'config', 'proxies.json');
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    return Array.isArray(config.proxies) ? config.proxies.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function parseProxy(proxyUrl) {
  try {
    const url = new URL(proxyUrl);
    if (!['http:', 'https:', 'socks5:'].includes(url.protocol)) return null;
    if (!url.hostname) return null;
    const proxy = { server: `${url.protocol}//${url.host}` };
    if (url.username) proxy.username = decodeURIComponent(url.username);
    if (url.password) proxy.password = decodeURIComponent(url.password);
    return proxy;
  } catch {
    return null;
  }
}

function configuredProxies() {
  return loadProxyUrls().map(parseProxy).filter(Boolean);
}

async function downloadAmazonImage(url) {
  const proxies = configuredProxies();
  if (proxies.length === 0) throw new Error('proxy_not_configured');

  const first = crypto.randomInt(proxies.length);
  let lastError = new Error('amazon_image_download_failed');
  for (let offset = 0; offset < proxies.length; offset += 1) {
    const proxy = proxies[(first + offset) % proxies.length];
    let context;
    try {
      context = await playwrightRequest.newContext({
        proxy,
        extraHTTPHeaders: {
          'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36',
          accept: 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
          'accept-language': 'en-US,en;q=0.9',
        },
      });
      const response = await context.get(url, {
        failOnStatusCode: false,
        maxRedirects: 5,
        timeout: IMAGE_TIMEOUT_MS,
      });
      if (!response.ok()) throw new Error(`upstream_http_${response.status()}`);
      if (!validAmazonImageUrl(response.url())) throw new Error('invalid_image_redirect');

      const headers = response.headers();
      const contentType = String(headers['content-type'] || '').split(';', 1)[0].toLowerCase();
      if (!contentType.startsWith('image/')) throw new Error('upstream_not_image');
      const declaredLength = Number.parseInt(headers['content-length'] || '0', 10) || 0;
      if (declaredLength > MAX_IMAGE_BYTES) throw new Error('image_too_large');

      const body = await response.body();
      if (body.length === 0) throw new Error('empty_image');
      if (body.length > MAX_IMAGE_BYTES) throw new Error('image_too_large');
      return { body, contentType };
    } catch (error) {
      lastError = error;
    } finally {
      if (context) await context.dispose().catch(() => {});
    }
  }
  throw lastError;
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new Error('request_too_large');
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}');
}

function scrape(url, pages) {
  return new Promise((resolve, reject) => {
    const args = ['assets/amazon_handler.js', url, '--pages', String(pages)];
    execFile(process.execPath, args, {
      cwd: '/app',
      env: process.env,
      timeout: JOB_TIMEOUT_MS,
      maxBuffer: MAX_RESULT_BYTES,
      windowsHide: true,
    }, (error, stdout, stderr) => {
      if (error) {
        const message = stderr.trim().split(/\r?\n/).slice(-1)[0] || error.message;
        return reject(new Error(message));
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch {
        reject(new Error('scraper_returned_invalid_json'));
      }
    });
  });
}

const server = http.createServer(async (req, res) => {
  const requestUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

  if (req.method === 'GET' && requestUrl.pathname === '/health') {
    return json(res, 200, {
      status: 'ok',
      proxy_configured: configuredProxies().length > 0,
      active_job: activeJob,
    });
  }

  const isScrape = req.method === 'POST' && requestUrl.pathname === '/scrape';
  const isImage = req.method === 'POST' && requestUrl.pathname === '/image';
  if (!isScrape && !isImage) {
    return json(res, 404, { error: 'not_found' });
  }
  if (!authorized(req)) return json(res, 401, { error: 'unauthorized' });
  if (configuredProxies().length === 0) {
    return json(res, 503, { error: 'proxy_not_configured' });
  }
  if (activeJob) return json(res, 429, { error: 'service_busy' });

  try {
    const body = await readJson(req);
    if (isImage) {
      const url = validAmazonImageUrl(String(body.url || '').trim());
      if (!url) return json(res, 400, { error: 'invalid_amazon_image_url' });
      activeJob = true;
      const image = await downloadAmazonImage(url);
      res.writeHead(200, {
        'content-type': image.contentType,
        'content-length': image.body.length,
        'content-disposition': 'inline; filename="amazon-image"',
        'cache-control': 'no-store',
        'x-content-type-options': 'nosniff',
      });
      res.end(image.body);
      return;
    }

    const url = validAmazonUrl(String(body.url || '').trim());
    if (!url) return json(res, 400, { error: 'invalid_amazon_url' });
    const pages = Math.max(1, Math.min(5, Number.parseInt(body.pages || '1', 10) || 1));
    activeJob = true;
    const result = await scrape(url, pages);
    return json(res, 200, result);
  } catch (error) {
    const status = error.message === 'request_too_large' ? 413 : 502;
    const kind = isImage ? 'image_download_failed' : 'scrape_failed';
    const message = isImage ? 'Amazon image could not be downloaded through the proxy pool.' : error.message;
    return json(res, status, { error: kind, message });
  } finally {
    activeJob = false;
  }
});

if (require.main === module) {
  server.listen(PORT, '0.0.0.0', () => {
    console.log(JSON.stringify({ status: 'listening', port: PORT }));
  });
}

module.exports = { validAmazonUrl, validAmazonImageUrl, parseProxy };
