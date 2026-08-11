import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const baseUrl = 'https://belladentclinik.kr.ua';
const apiUrl = 'https://bella-dent-api-production.up.railway.app';
const widths = [390, 768, 1440];
const runId = `browser-${Date.now()}`;
const outputDir = new URL('../test-results/live-browser-qa/', import.meta.url);
await mkdir(outputDir, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const browser = await chromium.launch({ headless: true });
try {
  for (const width of widths) {
    const context = await browser.newContext({ viewport: { width, height: width === 390 ? 900 : 1000 } });
    const page = await context.newPage();
    const pageErrors = [];
    const failedRequests = [];
    page.on('pageerror', (error) => pageErrors.push(error.message));
    page.on('requestfailed', (request) => {
      const url = request.url();
      if (url.startsWith(baseUrl) || url.startsWith(apiUrl)) failedRequests.push(`${request.method()} ${url}: ${request.failure()?.errorText}`);
    });

    const response = await page.goto(`${baseUrl}/`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    assert(response?.ok(), `${width}px homepage returned ${response?.status()}`);
    await page.waitForTimeout(2500);
    await page.locator('#lead-form').scrollIntoViewIfNeeded();

    const result = await page.evaluate(async ({ expectedApi }) => {
      const header = document.getElementById('site-header')?.getBoundingClientRect();
      const leadForm = document.getElementById('lead-form');
      const newsSection = document.getElementById('clinic-life');
      const apiResponse = await fetch(`${expectedApi}/api/news`);
      const news = await apiResponse.json();
      return {
        title: document.title,
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        headerLeft: header?.left,
        headerRight: header?.right,
        leadVisible: Boolean(leadForm && leadForm.getBoundingClientRect().height > 0),
        configuredApi: window.BELLA_API_BASE,
        apiStatus: apiResponse.status,
        newsCount: Array.isArray(news) ? news.length : -1,
        newsHidden: Boolean(newsSection?.hidden)
      };
    }, { expectedApi: apiUrl });

    assert(result.title.includes('Bella Dent'), `${width}px title is unexpected`);
    assert(result.overflow <= 1, `${width}px horizontal overflow: ${result.overflow}`);
    assert(result.headerLeft >= -1 && result.headerRight <= width + 1, `${width}px header is out of bounds`);
    assert(result.leadVisible, `${width}px lead form is not visible`);
    assert(result.configuredApi === apiUrl, `${width}px API configuration mismatch`);
    assert(result.apiStatus === 200, `${width}px browser API request returned ${result.apiStatus}`);
    assert(result.newsCount >= 0 && result.newsCount <= 3, `${width}px public news count is invalid: ${result.newsCount}`);
    assert(result.newsHidden === (result.newsCount === 0), `${width}px news section visibility does not match API content`);

    if (width === 390 && process.env.SKIP_LEAD !== '1') {
      await page.locator('#lead-name').fill('Production Browser QA');
      await page.locator('#lead-phone').fill('+380000000001');
      await page.locator('#lead-comment').fill(`Rendered live-form verification ${runId}`);
      await page.locator('#lead-form button[type="submit"]').click();
      await page.locator('#lead-form-status').filter({ hasText: 'Заявку передано адміністратору' }).waitFor({ state: 'visible', timeout: 30_000 });
    }

    assert(pageErrors.length === 0, `${width}px page errors: ${pageErrors.join(' | ')}`);
    assert(failedRequests.length === 0, `${width}px first-party request failures: ${failedRequests.join(' | ')}`);
    await page.screenshot({ path: fileURLToPath(new URL(`${width}px-home.png`, outputDir)), fullPage: true });

    const priceResponse = await page.goto(`${baseUrl}/price.html`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    assert(priceResponse?.ok(), `${width}px price page returned ${priceResponse?.status()}`);
    await page.locator('#price-main').waitFor({ state: 'visible' });
    const priceOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert(priceOverflow <= 1, `${width}px price page horizontal overflow: ${priceOverflow}`);
    console.log(`${width}px: homepage, API, form, and price page passed`);
    await context.close();
  }
  console.log(JSON.stringify({ runId, widths, status: 'passed' }));
} finally {
  await browser.close();
}
