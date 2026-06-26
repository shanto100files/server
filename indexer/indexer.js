/**
 * CinePix Pre-Indexer
 * Crawls provider sites and stores intermediate links in Cloudflare D1
 * Run: node indexer.js
 * 
 * Env Vars:
 *   D1_API_URL   - Cloudflare Worker API base URL
 *   D1_API_TOKEN - Bearer token for API (optional)
 *   TMDB_API_KEY - TMDB API key for title→ID matching (optional)
 *   MAX_POSTS    - Max posts to process per provider (default: 300)
 */

const D1_API_URL  = process.env.D1_API_URL  || 'https://cinepix-api.cinepixserver00.workers.dev';
const D1_API_TOKEN = process.env.D1_API_TOKEN || '';
const TMDB_KEY    = process.env.TMDB_API_KEY  || '';
const MAX_POSTS   = parseInt(process.env.MAX_POSTS || '300');
const DELAY_MS    = 1200; // between requests to avoid rate-limits

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

async function httpGet(url, headers = {}, timeout = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0',
        ...headers
      }
    });
    clearTimeout(timer);
    if (!res.ok) return null;
    return await res.text();
  } catch {
    clearTimeout(timer);
    return null;
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function extractQuality(text) {
  const m = (text || '').match(/(2160p|1080p|720p|480p|4K)/i);
  return m ? m[1] : 'HD';
}

function getFormat(url = '') {
  const l = url.toLowerCase();
  if (l.includes('.mkv') || l.includes('mkv')) return 'mkv';
  return 'mp4';
}

function slugify(url) {
  return url.replace(/\/$/, '').split('/').pop() || url;
}

// ─────────────────────────────────────────────────────────────────────────────
// D1 API
// ─────────────────────────────────────────────────────────────────────────────

const d1Headers = {
  'Content-Type': 'application/json',
  ...(D1_API_TOKEN ? { 'Authorization': `Bearer ${D1_API_TOKEN}` } : {})
};

async function d1Get(key, provider = 'index') {
  try {
    const res = await fetch(`${D1_API_URL}/api/cache?key=${encodeURIComponent(key)}&provider=${provider}`, {
      headers: d1Headers
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data?.data || null;
  } catch { return null; }
}

async function d1Set(key, data, provider = 'index') {
  try {
    const res = await fetch(`${D1_API_URL}/api/cache`, {
      method: 'POST',
      headers: d1Headers,
      body: JSON.stringify({ key, data, provider })
    });
    return res.ok;
  } catch { return false; }
}

// ─────────────────────────────────────────────────────────────────────────────
// TMDB Matching (optional)
// ─────────────────────────────────────────────────────────────────────────────

const tmdbCache = new Map();

async function findTmdbId(title, year = '') {
  if (!TMDB_KEY) return null;
  const cacheKey = `${title}|${year}`;
  if (tmdbCache.has(cacheKey)) return tmdbCache.get(cacheKey);

  const query = encodeURIComponent(title);
  const yearParam = year ? `&year=${year}` : '';

  // Try movie first
  let url = `https://api.themoviedb.org/3/search/movie?api_key=${TMDB_KEY}&query=${query}${yearParam}`;
  let html = await httpGet(url);
  if (html) {
    try {
      const data = JSON.parse(html);
      if (data.results?.length > 0) {
        const result = { id: data.results[0].id, type: 'movie' };
        tmdbCache.set(cacheKey, result);
        return result;
      }
    } catch {}
  }

  // Try TV
  url = `https://api.themoviedb.org/3/search/tv?api_key=${TMDB_KEY}&query=${query}${yearParam}`;
  html = await httpGet(url);
  if (html) {
    try {
      const data = JSON.parse(html);
      if (data.results?.length > 0) {
        const result = { id: data.results[0].id, type: 'tv' };
        tmdbCache.set(cacheKey, result);
        return result;
      }
    } catch {}
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Link Extraction Helpers
// ─────────────────────────────────────────────────────────────────────────────

const INTERMEDIATE_HOSTS = [
  'hubcloud', 'hubdrive', 'gdflix', 'cinecloud', 'filepress',
  'neodrive', 'fastdlserver', 'fxlinks', 'bonghd', 'pixeldrain',
  'mega.nz', 'gofile.io', 'mediafire'
];
const JUNK_HOSTS = [
  't.me', 'telegram', 'login', 'register', 'signup',
  'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
  'bit.ly', '.css', '.js', '.png', '.jpg', '.gif'
];

function isIntermediate(url) {
  return INTERMEDIATE_HOSTS.some(h => url.includes(h));
}

function isJunk(url) {
  return JUNK_HOSTS.some(h => url.toLowerCase().includes(h));
}

function extractLinksFromHtml(html, baseUrl = '') {
  const results = [];
  const seen = new Set();

  // Find all hrefs (both single and double quotes)
  const hrefRe = /href=["'](https?:\/\/[^"']+)["']/g;
  let m;
  while ((m = hrefRe.exec(html)) !== null) {
    const url = m[1].replace(/&amp;/g, '&');
    if (seen.has(url) || isJunk(url)) continue;
    if (!isIntermediate(url)) continue;
    seen.add(url);

    const idx = html.indexOf(m[0]);
    const context = html.substring(Math.max(0, idx - 100), idx + 100);
    const quality = extractQuality(context);
    const format = getFormat(url);

    results.push({ url, quality, format });
  }

  // Also check raw URLs in scripts/onclicks
  const rawRe = /(https?:\/\/[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\/[^\s"']*)?)/g;
  while ((m = rawRe.exec(html)) !== null) {
    const url = m[1].replace(/&amp;/g, '&');
    if (seen.has(url) || isJunk(url)) continue;
    if (!isIntermediate(url)) continue;
    seen.add(url);
    results.push({ url, quality: 'HD', format: getFormat(url) });
  }

  return results;
}

function extractEpisodeLabel(text) {
  const m = (text || '').match(/(?:Epi-?|Ep(?:isode)?\.?\s*|E)0*(\d+)/i);
  return m ? `E${m[1]}` : '';
}

function parseSlugTitle(url) {
  const slug = url.replace(/\/$/, '').split('/').pop() || '';
  return slug
    .replace(/-(1080p|720p|480p|4k|2160p|bluray|web-dl|webrip|dvdrip|hdcam|hevc|x264|x265|mkv|mp4|full|movie|season|episode|hindi|english|dual|audio).*/i, '')
    .replace(/-(\d{4})(-|$)/, '')
    .replace(/-/g, ' ')
    .trim();
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider: HDHub4U
// ─────────────────────────────────────────────────────────────────────────────

async function indexHDHub4U() {
  console.log('\n📦 [HDHub4U] Starting indexing...');
  const domain = 'https://new2.hdhub4u.limo';
  let indexed = 0;

  // Fetch sitemap index
  const sitemapIndex = await httpGet(`${domain}/sitemap.xml`);
  if (!sitemapIndex) { console.log('  ⚠ Sitemap not reachable'); return 0; }

  const postSitemaps = [...sitemapIndex.matchAll(/<loc>(https?:\/\/[^<]*post-sitemap[^<]*)<\/loc>/g)]
    .map(m => m[1]);

  const allUrls = [];
  for (const sm of postSitemaps.slice(0, 3)) { // last 3 sitemaps = newest posts
    const smHtml = await httpGet(sm);
    if (!smHtml) continue;
    const urls = [...smHtml.matchAll(/<loc>(https?:\/\/[^<]+)<\/loc>/g)].map(m => m[1]);
    allUrls.push(...urls);
    await sleep(DELAY_MS);
  }

  console.log(`  Found ${allUrls.length} post URLs`);

  for (const postUrl of allUrls.slice(0, MAX_POSTS)) {
    const slug = slugify(postUrl);
    const cacheKey = `indexed_hdhub4u_${slug}`;

    const existing = await d1Get(cacheKey);
    if (existing) { continue; } // already indexed

    const html = await httpGet(postUrl, { Referer: domain });
    await sleep(DELAY_MS);
    if (!html) continue;

    const links = extractLinksFromHtml(html, postUrl);
    if (links.length === 0) continue;

    const title = parseSlugTitle(postUrl);
    const yearM = postUrl.match(/(\d{4})/);
    const year = yearM ? yearM[1] : '';

    const record = { title, post_url: postUrl, year, provider: 'HDHub4U', links };

    const ok = await d1Set(cacheKey, record);

    // Also try to store by TMDB ID
    if (ok && TMDB_KEY) {
      const tmdb = await findTmdbId(title, year);
      if (tmdb) {
        const tmdbKey = `${tmdb.type}_${tmdb.id}`;
        const existing = await d1Get(tmdbKey, 'sources');
        const sources = existing || [];
        for (const l of links) {
          if (!sources.some(s => s.url === l.url)) {
            sources.push({ ...l, provider: 'HDHub4U' });
          }
        }
        await d1Set(tmdbKey, sources, 'sources');
        await sleep(500);
      }
    }

    indexed++;
    if (indexed % 20 === 0) console.log(`  ✅ HDHub4U: ${indexed} posts indexed`);
  }

  console.log(`  ✅ HDHub4U done: ${indexed} new posts indexed`);
  return indexed;
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider: CineFreak
// ─────────────────────────────────────────────────────────────────────────────

async function indexCineFreak() {
  console.log('\n📦 [CineFreak] Starting indexing...');
  const domain = 'https://cinefreak.net';
  let indexed = 0;
  const allUrls = new Set();

  // Crawl recent pages (page 1-10 of home/movies/series)
  const feeds = [
    `${domain}/`,
    `${domain}/movies/`,
    `${domain}/series/`,
    `${domain}/page/2/`,
    `${domain}/movies/page/2/`,
  ];

  for (const feedUrl of feeds) {
    const html = await httpGet(feedUrl, { Referer: domain });
    await sleep(DELAY_MS);
    if (!html) continue;

    const links = [...html.matchAll(/href="(https:\/\/cinefreak\.net\/[^"\/][^"]+)"/g)]
      .map(m => m[1])
      .filter(u => !u.includes('/page/') && !u.includes('/tag/') && !u.includes('/category/') && u !== domain + '/');

    for (const l of links) allUrls.add(l);
  }

  console.log(`  Found ${allUrls.size} post URLs`);

  for (const postUrl of [...allUrls].slice(0, MAX_POSTS)) {
    const slug = slugify(postUrl);
    const cacheKey = `indexed_cinefreak_${slug}`;

    const existing = await d1Get(cacheKey);
    if (existing) continue;

    const html = await httpGet(postUrl, { Cookie: 'xla=s4t', Referer: domain });
    await sleep(DELAY_MS);
    if (!html) continue;

    // Extract generate.php links and decode base64
    const genLinks = [];
    const genRe = /href="([^"]*generate\.php\?id=[^"]+)"/g;
    let m;
    while ((m = genRe.exec(html)) !== null) {
      const genUrl = m[1].replace(/&amp;/g, '&');
      const idM = genUrl.match(/id=([A-Za-z0-9+/=]+)/);
      if (idM) {
        try {
          let decoded = Buffer.from(idM[1], 'base64').toString('utf8');
          decoded = decoded.replace(/newgo\d+$/, '').replace('/x/', '/f/');
          genLinks.push({ url: decoded, quality: 'HD', format: 'mp4' });
        } catch {}
      }
    }

    const directLinks = extractLinksFromHtml(html, postUrl);
    const links = [...genLinks, ...directLinks].filter(l => l.url);
    if (links.length === 0) continue;

    const title = parseSlugTitle(postUrl);
    const yearM = postUrl.match(/(\d{4})/);
    const year = yearM ? yearM[1] : '';

    await d1Set(cacheKey, { title, post_url: postUrl, year, provider: 'CineFreak', links });

    if (TMDB_KEY) {
      const tmdb = await findTmdbId(title, year);
      if (tmdb) {
        const tmdbKey = `${tmdb.type}_${tmdb.id}`;
        const existing = await d1Get(tmdbKey, 'sources') || [];
        for (const l of links) {
          if (!existing.some(s => s.url === l.url)) existing.push({ ...l, provider: 'CineFreak' });
        }
        await d1Set(tmdbKey, existing, 'sources');
        await sleep(500);
      }
    }

    indexed++;
    if (indexed % 20 === 0) console.log(`  ✅ CineFreak: ${indexed} posts indexed`);
  }

  console.log(`  ✅ CineFreak done: ${indexed} new posts indexed`);
  return indexed;
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider: MLSBD
// ─────────────────────────────────────────────────────────────────────────────

async function indexMLSBD() {
  console.log('\n📦 [MLSBD] Starting indexing...');
  const domains = ['https://mlsbd.co', 'https://mlsbd.net', 'https://mlsbd.com'];
  let domain = domains[0];
  let allUrls = new Set();

  const categories = ['/', '/category/movies/', '/category/series/', '/category/web-series/', '/page/2/'];

  for (const d of domains) {
    const test = await httpGet(d);
    if (test) { domain = d; break; }
  }

  for (const cat of categories) {
    const url = `${domain}${cat}`;
    const html = await httpGet(url, { Referer: domain });
    await sleep(DELAY_MS);
    if (!html) continue;

    // extract domain hostname to make regex dynamic
    const hostname = new URL(domain).hostname.replace('.', '\\.');
    const re = new RegExp(`href="(https?:\/\/${hostname}\/[^"]+\/?)"`, 'g');
    
    const links = [...html.matchAll(re)]
      .map(m => m[1])
      .filter(u => !u.includes('/page/') && !u.includes('/tag/') && !u.includes('/category/') && !u.includes('/?') && u !== `${domain}/`);

    for (const l of links) allUrls.add(l);
  }

  console.log(`  Found ${allUrls.size} post URLs`);

  for (const postUrl of [...allUrls].slice(0, MAX_POSTS)) {
    const slug = slugify(postUrl);
    const cacheKey = `indexed_mlsbd_${slug}`;

    const existing = await d1Get(cacheKey);
    if (existing) continue;

    const html = await httpGet(postUrl, { Referer: domain });
    await sleep(DELAY_MS);
    if (!html) continue;

    // Resolve savelinks → extract outbound links
    const savelinkRe = /href="(https?:\/\/[^"]*savelinks[^"]*)"/g;
    const resolvedLinks = [];
    let sm;
    while ((sm = savelinkRe.exec(html)) !== null) {
      const slUrl = sm[1].replace(/&amp;/g, '&');
      const slHtml = await httpGet(slUrl, { Referer: postUrl });
      await sleep(DELAY_MS / 2);
      if (!slHtml) continue;
      const outLinks = extractLinksFromHtml(slHtml, slUrl);
      resolvedLinks.push(...outLinks);
    }

    const directLinks = extractLinksFromHtml(html, postUrl);
    const links = [...resolvedLinks, ...directLinks].filter(l => l.url);
    if (links.length === 0) continue;

    const title = parseSlugTitle(postUrl);
    const yearM = postUrl.match(/(\d{4})/);
    const year = yearM ? yearM[1] : '';

    await d1Set(cacheKey, { title, post_url: postUrl, year, provider: 'MLSBD', links });

    if (TMDB_KEY) {
      const tmdb = await findTmdbId(title, year);
      if (tmdb) {
        const tmdbKey = `${tmdb.type}_${tmdb.id}`;
        const existing = await d1Get(tmdbKey, 'sources') || [];
        for (const l of links) {
          if (!existing.some(s => s.url === l.url)) existing.push({ ...l, provider: 'MLSBD' });
        }
        await d1Set(tmdbKey, existing, 'sources');
        await sleep(500);
      }
    }

    indexed++;
    if (indexed % 20 === 0) console.log(`  ✅ MLSBD: ${indexed} posts indexed`);
  }

  console.log(`  ✅ MLSBD done: ${indexed} new posts indexed`);
  return indexed;
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider: BollyFlix
// ─────────────────────────────────────────────────────────────────────────────

async function indexBollyFlix() {
  console.log('\n📦 [BollyFlix] Starting indexing...');
  const domain = 'https://bollyflix.med';
  let indexed = 0;
  const allUrls = new Set();

  const pages = [`${domain}/`, `${domain}/page/2/`, `${domain}/page/3/`];
  for (const p of pages) {
    const html = await httpGet(p, { Referer: domain });
    await sleep(DELAY_MS);
    if (!html) continue;
    const links = [...html.matchAll(/href="(https:\/\/bollyflix\.[^"]+\/[^"]+)"/g)]
      .map(m => m[1])
      .filter(u => !u.includes('/page/') && !u.includes('/tag/') && !u.includes('/category/'));
    for (const l of links) allUrls.add(l);
  }

  console.log(`  Found ${allUrls.size} post URLs`);

  for (const postUrl of [...allUrls].slice(0, MAX_POSTS)) {
    const slug = slugify(postUrl);
    const cacheKey = `indexed_bollyflix_${slug}`;

    const existing = await d1Get(cacheKey);
    if (existing) continue;

    const html = await httpGet(postUrl, { Referer: domain });
    await sleep(DELAY_MS);
    if (!html) continue;

    // Resolve fxlinks → fastdlserver links
    const fxRe = /href="(https?:\/\/[^"]*fxlinks[^"]*)"/g;
    const resolvedLinks = [];
    let fm;
    while ((fm = fxRe.exec(html)) !== null) {
      const fxUrl = fm[1].replace(/&amp;/g, '&');
      const fxHtml = await httpGet(fxUrl, { Referer: postUrl });
      await sleep(DELAY_MS / 2);
      if (!fxHtml) continue;
      // Extract fastdlserver links from fxlinks page
      const fastLinks = [...fxHtml.matchAll(/href="(https?:\/\/[^"]*fastdlserver[^"]*)"/g)].map(m => ({
        url: m[1].replace(/&amp;/g, '&'),
        quality: extractQuality(fxHtml.substring(Math.max(0, fxHtml.indexOf(m[0]) - 100), fxHtml.indexOf(m[0]) + 100)),
        format: 'mp4'
      }));
      resolvedLinks.push(...fastLinks);
    }

    const directLinks = extractLinksFromHtml(html, postUrl);
    const links = [...resolvedLinks, ...directLinks].filter(l => l.url);
    if (links.length === 0) continue;

    const title = parseSlugTitle(postUrl);
    const yearM = postUrl.match(/(\d{4})/);
    const year = yearM ? yearM[1] : '';

    await d1Set(cacheKey, { title, post_url: postUrl, year, provider: 'BollyFlix', links });

    if (TMDB_KEY) {
      const tmdb = await findTmdbId(title, year);
      if (tmdb) {
        const tmdbKey = `${tmdb.type}_${tmdb.id}`;
        const existing = await d1Get(tmdbKey, 'sources') || [];
        for (const l of links) {
          if (!existing.some(s => s.url === l.url)) existing.push({ ...l, provider: 'BollyFlix' });
        }
        await d1Set(tmdbKey, existing, 'sources');
        await sleep(500);
      }
    }

    indexed++;
    if (indexed % 20 === 0) console.log(`  ✅ BollyFlix: ${indexed} posts indexed`);
  }

  console.log(`  ✅ BollyFlix done: ${indexed} new posts indexed`);
  return indexed;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

async function main() {
  console.log('🚀 CinePix Indexer Started');
  console.log(`   D1 API: ${D1_API_URL}`);
  console.log(`   Max posts per provider: ${MAX_POSTS}`);
  console.log(`   TMDB matching: ${TMDB_KEY ? 'enabled' : 'disabled'}`);
  console.log('');

  const results = {};

  // Run providers in sequence to avoid overwhelming target sites
  results.hdhub4u = await indexHDHub4U();
  await sleep(3000);

  results.cinefreak = await indexCineFreak();
  await sleep(3000);

  results.mlsbd = await indexMLSBD();
  await sleep(3000);

  results.bollyflix = await indexBollyFlix();

  console.log('\n\n✅ Indexing Complete!');
  console.log('─'.repeat(40));
  for (const [provider, count] of Object.entries(results)) {
    console.log(`   ${provider.padEnd(12)}: ${count} new posts`);
  }
  console.log(`   TOTAL       : ${Object.values(results).reduce((a, b) => a + b, 0)} new posts`);
  console.log('─'.repeat(40));
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
