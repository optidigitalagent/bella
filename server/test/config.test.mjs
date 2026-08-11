import test from 'node:test';
import assert from 'node:assert/strict';
import { loadConfig } from '../src/config.mjs';

const production = {
  NODE_ENV: 'production',
  PUBLIC_BASE_URL: 'https://bella-dent-api-production.up.railway.app',
  TELEGRAM_BOT_TOKEN: 'token',
  TELEGRAM_ADMIN_IDS: '12345',
  TELEGRAM_WEBHOOK_SECRET: 'safe_secret',
  CLOUDINARY_CLOUD_NAME: 'cloud',
  CLOUDINARY_API_KEY: 'key',
  CLOUDINARY_API_SECRET: 'secret'
};

test('production requires DATABASE_URL and no Google variables', () => {
  assert.throws(() => loadConfig(production), /DATABASE_URL/);
  const config = loadConfig({ ...production, DATABASE_URL: 'postgresql://db.internal:5432/railway' });
  assert.equal(config.database.databaseUrl, 'postgresql://db.internal:5432/railway');
  assert.equal('google' in config, false);
});
