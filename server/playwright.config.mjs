import { defineConfig } from '@playwright/test';

const widths = [360, 390, 430, 768, 1024, 1280, 1440];
const qaPort = Number(process.env.QA_PORT || 43917);
const qaBaseUrl = `http://127.0.0.1:${qaPort}`;

export default defineConfig({
  testDir: './qa',
  outputDir: './test-results/browser-qa',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: qaBaseUrl,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure'
  },
  webServer: {
    command: 'npm run qa:serve',
    url: `${qaBaseUrl}/health-for-qa`,
    env: { QA_PORT: String(qaPort) },
    reuseExistingServer: true,
    timeout: 30_000
  },
  projects: widths.map((width) => ({
    name: `${width}px`,
    use: { viewport: { width, height: width <= 430 ? 900 : 1000 } }
  }))
});
