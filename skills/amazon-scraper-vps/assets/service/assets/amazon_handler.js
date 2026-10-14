const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
chromium.use(stealth);

const fs = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const targetUrl = args.find(a => a.startsWith('http'));
const maxPages = parseInt(args.find((a, i) => args[i-1] === '--pages') || '1');
const outputFile = args.find((a, i) => args[i-1] === '--output');
const concurrency = parseInt(args.find((a, i) => args[i-1] === '--concurrency') || '1');
const queriesArg = args.find((a, i) => args[i-1] === '--queries');
const queries = queriesArg ? queriesArg.split(',').map(s => s.trim()).filter(Boolean) : null;
const bsrMode = args.includes('--bsr');
const bsrCategories = (args.find((a, i) => args[i-1] === '--bsr-cats') || 'electronics,home,office-products,tools').split(',').map(s => s.trim());

if (!targetUrl && !queries && !bsrMode) {
    console.error('Usage: node assets/amazon_handler.js <AMAZON_URL> [--pages N] [--output path.json] [--concurrency N]');
    console.error('   OR: --queries "q1,q2,q3" [--pages N]');
    console.error('   OR: --bsr [--bsr-cats electronics,home,office-products,tools]');
    process.exit(1);
}

function saveResult(data) {
    if (outputFile) {
        const outPath = path.isAbsolute(outputFile) ? outputFile : path.join('/data', outputFile);
        const dir = path.dirname(outPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(outPath, JSON.stringify(data, null, 2));
        console.error(`Result saved to: ${outPath}`);
    }
}

function detectPageType(url) {
    if (url.includes('/zgbs/') || url.includes('/bestsellers/')) return 'bestsellers';
    if (url.includes('/zg/new-releases/')) return 'new-releases';
    if (url.includes('/zg/movers-and-shakers/')) return 'movers-shakers';
    if (url.includes('/dp/') || url.includes('/gp/product/')) return 'product-detail';
    if (url.includes('/s?') || url.includes('/s/')) return 'search';
    return 'generic';
}

const pageType = targetUrl ? detectPageType(targetUrl) : 'generic';

// ---- Proxy rotation setup ----
// Load built-in proxy config, allow env vars to override
function loadProxies() {
    const single = process.env.AMAZON_PROXY;
    const multi = process.env.AMAZON_PROXIES;
    if (multi) return multi.split(',').map(s => s.trim()).filter(Boolean);
    if (single) return [single];
    try {
        const configPath = path.join(__dirname, '..', 'config', 'proxies.json');
        if (fs.existsSync(configPath)) {
            const cfg = JSON.parse(fs.readFileSync(configPath, 'utf8'));
            if (cfg.proxies && cfg.proxies.length > 0) {
                return cfg.proxies;
            }
        }
    } catch (e) {
        console.error('Failed to load config/proxies.json:', e.message);
    }
    return [];
}

const PROXY_LIST = loadProxies();
if (PROXY_LIST.length === 0) {
    console.error(JSON.stringify({
        status: 'ERROR',
        message: 'Proxy configuration is required; direct Amazon access is disabled.'
    }));
    process.exit(2);
}

let proxyIdx = 0;
function getNextProxy() {
    if (PROXY_LIST.length === 0) return null;
    const p = PROXY_LIST[proxyIdx % PROXY_LIST.length];
    proxyIdx++;
    return p;
}

function parseProxy(proxyUrl) {
    try {
        const url = new URL(proxyUrl);
        return {
            server: `${url.protocol}//${url.host}`,
            username: decodeURIComponent(url.username),
            password: decodeURIComponent(url.password)
        };
    } catch (e) {
        console.error('Invalid proxy URL format:', proxyUrl);
        return null;
    }
}

async function createContext(browser) {
    const proxyUrl = getNextProxy();
    const contextOptions = {
        viewport: { width: 1920, height: 1080 },
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        extraHTTPHeaders: {
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'identity',
            'Sec-Ch-Ua': '"Google Chrome";v="123", "Not:A-Brand";v="8"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document'
        }
    };
    if (proxyUrl) {
        const parsed = parseProxy(proxyUrl);
        if (parsed) {
            contextOptions.proxy = parsed;
            console.error(`Using proxy: ${parsed.server} (user: ${parsed.username})`);
        }
    }
    const context = await browser.newContext(contextOptions);
    await context.setExtraHTTPHeaders({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'identity',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Google Chrome";v="123", "Not:A-Brand";v="8"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    });
    return context;
}

async function runCrawler() {
    // ============== Multi-query / BSR / single-URL dispatch ==============
    let jobs = [];
    if (bsrMode) {
        // BSR mode: each category -> 1 URL with --pages 2 (BSR caps at 2 pages = ~60 products)
        for (const cat of bsrCategories) {
            jobs.push({ url: `https://www.amazon.com/gp/bestsellers/${cat}`, pages: 2, label: `BSR/${cat}` });
        }
    } else if (queries) {
        for (const q of queries) {
            jobs.push({ url: `https://www.amazon.com/s?k=${encodeURIComponent(q)}`, pages: maxPages, label: `search/${q}` });
        }
    } else {
        jobs.push({ url: targetUrl, pages: maxPages, label: 'single' });
    }

    const browser = await chromium.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    let context = null;

    try {
        // ============== Worker pool: process jobs with limited concurrency ==============
        const extractFromPage = async (page, pType) => {
            let products = [];

            if (pType === 'bestsellers' || pType === 'new-releases' || pType === 'movers-shakers') {
                products = await page.evaluate(() => {
                    const items = [];
                    const cards = document.querySelectorAll('[data-asin]');

                    if (cards.length > 0) {
                        cards.forEach(card => {
                            try {
                                const rankEl = card.querySelector('.zg-bdg-text, [class*="zg-badge"]');
                                const titleEl = card.querySelector('a span, ._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y, .p13n-sc-truncate');
                                const ratingEl = card.querySelector('[class*="a-icon-alt"]');
                                const reviewEl = card.querySelector('[class*="a-size-small"]');
                                const priceEl = card.querySelector('.p13n-sc-price, ._cDEzb_p13n-sc-price_3mJ9Z, .a-price .a-offscreen');
                                const imgEl = card.querySelector('img');
                                const linkEl = card.querySelector('a[href*="/dp/"]');
                                const asin = card.getAttribute('data-asin') || (linkEl && linkEl.href && linkEl.href.match(/\/dp\/([A-Z0-9]{10})/) ? linkEl.href.match(/\/dp\/([A-Z0-9]{10})/)[1] : null);

                                let boughtPastMonth = null;
                                card.querySelectorAll('span').forEach(s => {
                                    const t = s.textContent.trim();
                                    if (t.match(/bought in past month/i)) {
                                        const m = t.match(/([\d,.]+[KkMm]?\+?)\s*bought/i);
                                        boughtPastMonth = m ? m[1] : t;
                                    }
                                });

                                const rank = rankEl ? parseInt(rankEl.textContent.replace('#', '')) : null;
                                const title = titleEl ? titleEl.textContent.trim() : null;
                                const rating = ratingEl ? parseFloat(ratingEl.textContent) : null;
                                const reviews = reviewEl ? parseInt(reviewEl.textContent.replace(/[^0-9]/g, '')) : null;
                                const priceText = priceEl ? priceEl.textContent.trim() : null;
                                const price = priceText ? parseFloat(priceText.replace(/[^0-9.]/g, '')) : null;
                                const image = imgEl ? imgEl.src : null;
                                const url = linkEl ? linkEl.href : null;

                                if (title) {
                                    items.push({ rank, title, rating, reviews, price, priceStr: priceText, asin, image, url, boughtPastMonth });
                                }
                            } catch (e) {}
                        });
                    }

                    if (items.length === 0) {
                        const text = document.body.innerText;
                        const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
                        let currentRank = null;
                        let currentProduct = {};

                        for (const line of lines) {
                            const rankMatch = line.match(/^#(\d+)$/);
                            if (rankMatch) {
                                if (currentRank && currentProduct.title) items.push(currentProduct);
                                currentRank = parseInt(rankMatch[1]);
                                currentProduct = { rank: currentRank };
                                continue;
                            }
                            if (currentRank) {
                                if (line.match(/^([\d.]+) out of 5 stars$/)) {
                                    currentProduct.rating = parseFloat(line);
                                } else if (line.match(/^\$([\d,.]+)$/)) {
                                    currentProduct.price = parseFloat(line.replace(/[$,]/g, ''));
                                    currentProduct.priceStr = line;
                                } else if (line.match(/^\s*[\d,]+\s*$/) && !currentProduct.reviews && currentProduct.rating) {
                                    currentProduct.reviews = parseInt(line.replace(/,/g, ''));
                                } else if (line.match(/bought in past month/i)) {
                                    const m = line.match(/([\d,.]+[KkMm]?\+?)\s*bought/i);
                                    currentProduct.boughtPastMonth = m ? m[1] : line;
                                } else if (!currentProduct.title && line.length > 10
                                    && !line.includes('out of 5') && !line.includes('Best Seller')
                                    && !line.includes('Previous page') && !line.includes('Next page')) {
                                    currentProduct.title = line;
                                }
                            }
                        }
                        if (currentRank && currentProduct.title) items.push(currentProduct);
                    }
                    return items;
                });

            } else if (pType === 'product-detail') {
                products = await page.evaluate(() => {
                    const title = (document.querySelector('#productTitle') || {}).textContent?.trim();
                    const priceEl = document.querySelector('.a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice');
                    const priceStr = priceEl ? priceEl.textContent.trim() : null;
                    const price = priceStr ? parseFloat(priceStr.replace(/[^0-9.]/g, '')) : null;
                    const ratingEl = document.querySelector('#acrPopover .a-icon-alt');
                    const rating = ratingEl ? parseFloat(ratingEl.textContent) : null;
                    const reviewsEl = document.querySelector('#acrCustomerReviewText');
                    const reviews = reviewsEl ? parseInt(reviewsEl.textContent.replace(/[^0-9]/g, '')) : null;
                    const asin = (document.querySelector('[data-asin]') || {}).getAttribute?.('data-asin') || (window.location.pathname.match(/\/dp\/([A-Z0-9]{10})/) || [])[1];
                    const brand = (document.querySelector('#bylineInfo') || {}).textContent?.trim();
                    const image = (document.querySelector('#landingImage, #imgBlkFront') || {}).src;
                    const bsrMatch = document.body.innerText.match(/Best Sellers Rank.*?#([\d,]+)/);
                    const bsr = bsrMatch ? parseInt(bsrMatch[1].replace(/,/g, '')) : null;
                    const breadcrumbs = Array.from(document.querySelectorAll('#wayfinding-breadcrumbs_feature_div a')).map(a => a.textContent.trim());
                    const bullets = Array.from(document.querySelectorAll('#feature-bullets li span')).map(s => s.textContent.trim()).filter(Boolean);

                    let boughtPastMonth = null;
                    const boughtMatch = document.body.innerText.match(/([\d,.]+[KkMm]?\+?)\s*bought in past month/i);
                    if (boughtMatch) boughtPastMonth = boughtMatch[1];

                    const dateMatch = document.body.innerText.match(/Date First Available\s*[:\n]\s*([A-Za-z]+ \d+,? \d{4})/);
                    const dateFirstAvailable = dateMatch ? dateMatch[1] : null;

                    const details = {};
                    document.querySelectorAll('#productDetails_techSpec_section_1 tr, #detailBullets_feature_div li').forEach(row => {
                        const key = (row.querySelector('th, .a-text-bold') || {}).textContent?.trim()?.replace(/[:\s]+$/, '');
                        const val = (row.querySelector('td, span:not(.a-text-bold)') || {}).textContent?.trim();
                        if (key && val) details[key] = val;
                    });

                    return [{ title, price, priceStr, rating, reviews, asin, brand, image, bsr, boughtPastMonth, dateFirstAvailable, category: breadcrumbs, bullets, details }];
                });

            } else if (pType === 'search') {
                products = await page.evaluate(() => {
                    const items = [];
                    document.querySelectorAll('[data-component-type="s-search-result"]').forEach(card => {
                        try {
                            const asin = card.getAttribute('data-asin');
                            const titleEl = card.querySelector('h2 a span') || card.querySelector('h2 span');
                            const priceEl = card.querySelector('.a-price .a-offscreen');
                            const ratingEl = card.querySelector('.a-icon-alt');
                            const reviewEl = card.querySelector('[class*="s-link-style"] .a-size-base');
                            const imgEl = card.querySelector('.s-image');
                            const linkEl = card.querySelector('h2 a');
                            const sponsoredEl = card.querySelector('.s-label-popover-default');

                            let boughtPastMonth = null;
                            card.querySelectorAll('span').forEach(s => {
                                const t = s.textContent.trim();
                                if (t.match(/bought in past month/i)) {
                                    const m = t.match(/([\d,.]+[KkMm]?\+?)\s*bought/i);
                                    boughtPastMonth = m ? m[1] : t;
                                }
                            });

                            items.push({
                                asin,
                                title: titleEl ? titleEl.textContent.trim() : null,
                                price: priceEl ? parseFloat(priceEl.textContent.replace(/[^0-9.]/g, '')) : null,
                                priceStr: priceEl ? priceEl.textContent.trim() : null,
                                rating: ratingEl ? parseFloat(ratingEl.textContent) : null,
                                reviews: reviewEl ? parseInt(reviewEl.textContent.replace(/[^0-9]/g, '')) : null,
                                image: imgEl ? imgEl.src : null,
                                url: linkEl ? 'https://www.amazon.com' + linkEl.getAttribute('href') : null,
                                boughtPastMonth,
                                sponsored: !!sponsoredEl
                            });
                        } catch (e) {}
                    });
                    return items;
                });

            } else {
                // Generic fallback
                const content = await page.evaluate(() => document.body.innerText);
                return [{ _generic: true, data: content.substring(0, 10000) }];
            }

            return products;
        };

        const runJob = async (job) => {
            const t0 = Date.now();
            console.error(`[${job.label}] starting...`);
            const jobPageType = detectPageType(job.url);
            let jobProducts = [];
            const proxyCount = Math.max(PROXY_LIST.length, 1);

            for (let pg = 1; pg <= job.pages; pg++) {
                let url = job.url;
                if (pg > 1) url = job.url.includes('?') ? `${job.url}&pg=${pg}` : `${job.url}?pg=${pg}`;

                let success = false;
                let lastErr = null;
                let jobContext = null;
                let jobPage = null;

                for (let attempt = 0; attempt < proxyCount; attempt++) {
                    try {
                        jobContext = await createContext(browser);
                        jobPage = await jobContext.newPage();
                        await jobPage.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });

                        if (jobPageType === 'search') {
                            try {
                                await jobPage.waitForSelector('[data-component-type="s-search-result"]', { timeout: 15000 });
                                await jobPage.waitForFunction(() => {
                                    const cards = document.querySelectorAll('[data-component-type="s-search-result"] h2 a span, [data-component-type="s-search-result"] h2 span');
                                    let nonEmpty = 0;
                                    for (const c of cards) { if (c.textContent.trim().length > 5) nonEmpty++; }
                                    return nonEmpty >= 10;
                                }, { timeout: 20000 });
                            } catch(e) { console.error(`[${job.label}] search wait:`, e.message); }
                        } else {
                            await jobPage.waitForTimeout(3000);
                        }
                        await jobPage.evaluate(async () => {
                            for (let i = 0; i < 5; i++) { window.scrollBy(0, window.innerHeight); await new Promise(r => setTimeout(r, 500)); }
                            window.scrollTo(0, 0);
                        });

                        const pageProducts = await extractFromPage(jobPage, jobPageType);
                        if (pg === 1 && pageProducts.length === 0 && jobPageType === 'search') {
                            throw new Error('No products extracted - search page may be blocked');
                        }
                        jobProducts.push(...pageProducts);
                        success = true;
                        break;
                    } catch (err) {
                        lastErr = err;
                        console.error(`[${job.label}] attempt ${attempt + 1} failed: ${err.message}`);
                        if (jobPage) { try { await jobPage.close(); } catch(e) {} }
                        if (jobContext) { try { await jobContext.close(); } catch(e) {} }
                    }
                }

                if (!success) {
                    console.error(`[${job.label}] ALL PROXIES FAILED on page ${pg}: ${lastErr?.message}`);
                }

                if (jobPage) { try { await jobPage.close(); } catch(e) {} }
                if (jobContext) { try { await jobContext.close(); } catch(e) {} }
                if (pg < job.pages) await new Promise(r => setTimeout(r, 1500));
            }

            console.error(`[${job.label}] done: ${jobProducts.length} products in ${(Date.now()-t0)/1000}s`);
            return { job, products: jobProducts };
        };

        const workerPool = async (items, conc) => {
            const results = new Array(items.length);
            let idx = 0;
            const worker = async () => {
                while (idx < items.length) {
                    const myIdx = idx++;
                    results[myIdx] = await runJob(items[myIdx]);
                }
            };
            const workers = [];
            for (let i = 0; i < Math.min(conc, items.length); i++) workers.push(worker());
            await Promise.all(workers);
            return results;
        };

        const conc = Math.max(1, Math.min(concurrency, jobs.length, PROXY_LIST.length || 1));
        console.error(`Running ${jobs.length} jobs with concurrency=${conc}`);
        const t0 = Date.now();
        const results = await workerPool(jobs, conc);

        // Merge all results
        const seenAsin = new Set();
        const allProducts = [];
        const sourcesByAsin = {};
        for (const r of results) {
            for (const p of (r.products || [])) {
                if (p.asin && !seenAsin.has(p.asin)) {
                    seenAsin.add(p.asin);
                    p._source = r.job.label;
                    allProducts.push(p);
                } else if (p.asin && seenAsin.has(p.asin)) {
                    // already have it, merge source
                    if (!sourcesByAsin[p.asin]) sourcesByAsin[p.asin] = [p._source || r.job.label];
                    sourcesByAsin[p.asin].push(r.job.label);
                }
            }
        }
        // add merged sources
        for (const p of allProducts) {
            if (sourcesByAsin[p.asin]) {
                const all = new Set([p._source, ...sourcesByAsin[p.asin]]);
                p._sources = Array.from(all);
            }
        }

        // Deduplicate by ASIN within each job result already done, but cross-job merge handled above
        // Save
        const result = {
            status: 'SUCCESS',
            mode: bsrMode ? 'bsr' : (queries ? 'multi-query' : 'single'),
            jobs: jobs.map(j => j.label),
            concurrency: conc,
            totalJobs: jobs.length,
            totalProducts: allProducts.length,
            uniqueAsins: seenAsin.size,
            durationSeconds: Math.round((Date.now() - t0) / 1000),
            scrapedAt: new Date().toISOString(),
            products: allProducts
        };
        console.log(JSON.stringify(result));
        saveResult(result);

    } catch (err) {
        const errorResult = { status: 'ERROR', message: err.message, stack: err.stack };
        console.error(JSON.stringify(errorResult));
        saveResult(errorResult);
        process.exit(1);
    } finally {
        if (context) { try { await context.close(); } catch(e) {} }
        await browser.close();
    }
}

runCrawler();
