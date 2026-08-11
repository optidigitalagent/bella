import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('https://docs.google.com/**', (route) => route.abort());
});

test('Clinic Life, lead form, and existing homepage remain responsive', async ({ page }, testInfo) => {
  const browserErrors = [];
  page.on('pageerror', (error) => browserErrors.push(error.message));
  await page.goto('/index.html', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#clinic-life')).toBeVisible();
  await expect(page.locator('#clinic-life .clinic-life-card')).toHaveCount(3);
  await expect(page.locator('#doctors-grid .doctor-card')).toHaveCount(5);

  const orderIsCorrect = await page.evaluate(() => {
    const clinicLife = document.getElementById('clinic-life');
    const reviews = document.getElementById('reviews');
    return Boolean(clinicLife.compareDocumentPosition(reviews) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(orderIsCorrect).toBe(true);

  const metrics = await page.evaluate(() => {
    const header = document.getElementById('site-header').getBoundingClientRect();
    const grid = document.getElementById('clinic-life-grid');
    const first = grid.children[0].getBoundingClientRect();
    const second = grid.children[1].getBoundingClientRect();
    return {
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      headerLeft: header.left,
      headerRight: header.right,
      gridDisplay: getComputedStyle(grid).display,
      firstWidth: first.width,
      secondWidth: second.width,
      gridWidth: grid.clientWidth,
      firstHeight: first.height,
      secondHeight: second.height
    };
  });
  expect(metrics.overflow).toBeLessThanOrEqual(1);
  expect(metrics.headerLeft).toBeGreaterThanOrEqual(-1);
  expect(metrics.headerRight).toBeLessThanOrEqual(testInfo.project.use.viewport.width + 1);

  const width = testInfo.project.use.viewport.width;
  if (width <= 900) {
    expect(metrics.gridDisplay).toBe('flex');
    expect(metrics.firstWidth).toBeGreaterThan(metrics.gridWidth * 0.9);
    await expect(page.locator('#clinic-life-dots .clinic-life-dot')).toHaveCount(3);
    await page.locator('#clinic-life-dots .clinic-life-dot').nth(1).click();
    await expect(page.locator('#clinic-life-dots .clinic-life-dot').nth(1)).toHaveAttribute('aria-current', 'true');
  } else {
    expect(metrics.gridDisplay).toBe('grid');
    expect(metrics.firstHeight).toBeGreaterThan(metrics.secondHeight);
  }

  const video = page.locator('#clinic-life video');
  await expect(video).toHaveCount(1);
  expect(await video.evaluate((element) => ({ autoplay: element.autoplay, controls: element.controls }))).toEqual({ autoplay: false, controls: true });

  await page.locator('#lead-name').fill('QA Пацієнт');
  await page.locator('#lead-phone').fill('+380671234567');
  await page.locator('#lead-comment').fill('Browser QA');
  await page.locator('#lead-form button[type="submit"]').click();
  await expect(page.locator('#lead-form-status')).toContainText('Заявку передано адміністратору');

  expect(browserErrors).toEqual([]);
  await page.screenshot({ path: `test-results/browser-qa/${width}px-home.png`, fullPage: true });
});

test('price page remains rendered without horizontal overflow', async ({ page }) => {
  await page.goto('/price.html', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#price-main')).not.toBeEmpty();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
