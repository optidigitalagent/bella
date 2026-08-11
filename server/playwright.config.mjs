import { defineConfig } from '@playwright/test';

const widths = [360, 390, 430, 768, 1024, 1280, 1440];

export default defineConfig({
  testDir: './qa',
  outputDir: './test-results/browser-qa',
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure'
  },
  webServer: {
    command: 'npm run qa:serve',
    url: 'http://127.0.0.1:4173/health-for-qa',
    reuseExistingServer: true,
    timeout: 30_000
  },
  projects: widths.map((width) => ({
    name: `${width}px`,
    use: { viewport: { width, height: width <= 430 ? 900 : 1000 } }
  }))
});
