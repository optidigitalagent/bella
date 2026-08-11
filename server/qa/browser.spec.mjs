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
    const contacts = document.getElementById('contacts');
    return Boolean(reviews.compareDocumentPosition(clinicLife) & Node.DOCUMENT_POSITION_FOLLOWING) &&
      Boolean(clinicLife.compareDocumentPosition(contacts) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(orderIsCorrect).toBe(true);

  const metrics = await page.evaluate(() => {
    const header = document.getElementById('site-header').getBoundingClientRect();
    const grid = document.getElementById('clinic-life-grid');
    const first = grid.children[0].getBoundingClientRect();
    const second = grid.children[1].getBoundingClientRect();
    const third = grid.children[2].getBoundingClientRect();
    const gridRect = grid.getBoundingClientRect();
    return {
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      headerLeft: header.left,
      headerRight: header.right,
      gridDisplay: getComputedStyle(grid).display,
      firstWidth: first.width,
      secondWidth: second.width,
      gridWidth: grid.clientWidth,
      gridRight: gridRect.right,
      secondLeft: second.left,
      firstHeight: first.height,
      secondHeight: second.height,
      thirdHeight: third.height,
      firstCardWidth: first.width,
      secondCardWidth: second.width
    };
  });
  expect(metrics.overflow).toBeLessThanOrEqual(1);
  expect(metrics.headerLeft).toBeGreaterThanOrEqual(-1);
  expect(metrics.headerRight).toBeLessThanOrEqual(testInfo.project.use.viewport.width + 1);

  const width = testInfo.project.use.viewport.width;
  console.log('Clinic Life metrics', width, metrics);
  if (width <= 900) {
    expect(metrics.gridDisplay).toBe('flex');
    expect(metrics.firstWidth).toBeGreaterThanOrEqual(metrics.gridWidth - 1);
    expect(metrics.secondLeft).toBeGreaterThanOrEqual(metrics.gridRight + 10);
    await expect(page.locator('#clinic-life-dots .clinic-life-dot')).toHaveCount(3);
    await page.locator('#clinic-life-dots .clinic-life-dot').nth(1).click();
    await expect(page.locator('#clinic-life-dots .clinic-life-dot').nth(1)).toHaveAttribute('aria-current', 'true');
    await expect.poll(() => page.locator('#clinic-life-grid').evaluate((element) => {
      const activeCard = element.children[1];
      return Math.abs(activeCard.offsetLeft - element.offsetLeft - element.scrollLeft);
    })).toBeLessThanOrEqual(1);
    await page.locator('#clinic-life-dots .clinic-life-dot').first().click();
    await expect.poll(() => page.locator('#clinic-life-grid').evaluate((element) => Math.abs(element.scrollLeft))).toBeLessThanOrEqual(1);
  } else {
    expect(metrics.gridDisplay).toBe('grid');
    expect(metrics.firstHeight).toBeGreaterThan(metrics.secondHeight);
    expect(metrics.firstCardWidth).toBeGreaterThan(metrics.secondCardWidth);
    expect(Math.abs(metrics.secondHeight - metrics.thirdHeight)).toBeLessThanOrEqual(2);
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
  await page.locator('#clinic-life').screenshot({ path: `test-results/browser-qa/${width}px-clinic-life.png` });
});

test('Clinic Life keeps a branded empty state for zero news', async ({ page }, testInfo) => {
  await page.route('**/api/news', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: '[]'
  }));
  await page.goto('/index.html?qa=empty', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#clinic-life')).toBeVisible();
  await expect(page.locator('#clinic-life-grid')).toHaveAttribute('data-count', '0');
  await expect(page.locator('#clinic-life .clinic-life-empty')).toContainText('Незабаром тут зʼявляться');
  await expect(page.locator('#clinic-life .clinic-life-card')).toHaveCount(0);
  await expect(page.locator('#clinic-life-dots')).toBeHidden();
  const width = testInfo.project.use.viewport.width;
  await page.locator('#clinic-life').screenshot({ path: `test-results/browser-qa/${width}px-clinic-life-empty.png` });
});

test('Clinic Life renders one, two, and three news layouts without empty slots', async ({ page }, testInfo) => {
  const items = [
    {
      id: 'qa-1',
      title: 'Перша новина Bella Dent',
      description: 'Спокійна розповідь про подію клініки та турботу про пацієнтів.',
      mediaType: 'image',
      mediaUrl: 'https://res.cloudinary.com/demo/image/upload/sample.jpg',
      instagramUrl: '',
      publishedAt: '2026-08-11T09:00:00.000Z'
    },
    {
      id: 'qa-2',
      title: 'Друга новина Bella Dent',
      description: 'Команда продовжує навчання та вдосконалює клінічні навички.',
      mediaType: 'image',
      mediaUrl: 'https://res.cloudinary.com/demo/image/upload/couple.jpg',
      instagramUrl: '',
      publishedAt: '2026-08-10T09:00:00.000Z'
    },
    {
      id: 'qa-3',
      title: 'Третя новина Bella Dent',
      description: 'Сучасні технології допомагають зробити лікування передбачуваним.',
      mediaType: 'video',
      mediaUrl: 'https://res.cloudinary.com/demo/video/upload/dog.mp4',
      instagramUrl: '',
      publishedAt: '2026-08-09T09:00:00.000Z'
    }
  ];
  let count = 1;
  await page.route('**/api/news', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(items.slice(0, count))
  }));

  for (count = 1; count <= 3; count += 1) {
    await page.goto(`/index.html?qa=count-${count}`, { waitUntil: 'domcontentloaded' });
    const grid = page.locator('#clinic-life-grid');
    await expect(grid).toHaveAttribute('data-count', String(count));
    await expect(grid.locator('.clinic-life-card')).toHaveCount(count);
    await expect(grid.locator('.clinic-life-empty')).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);

    if (testInfo.project.use.viewport.width > 900 && count === 2) {
      const widths = await grid.locator('.clinic-life-card').evaluateAll((cards) => cards.map((card) => card.getBoundingClientRect().width));
      expect(Math.abs(widths[0] - widths[1])).toBeLessThanOrEqual(2);
    }
  }
});

test('price page remains rendered without horizontal overflow', async ({ page }) => {
  await page.goto('/price.html', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#price-main')).not.toBeEmpty();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
