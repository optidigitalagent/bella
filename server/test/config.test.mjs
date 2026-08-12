import test from 'node:test';
import assert from 'node:assert/strict';
import { loadConfig } from '../src/config.mjs';

const production = {
  NODE_ENV: 'production',
  PUBLIC_BASE_URL: 'https://bella-dent-api-production.up.railway.app',
  TELEGRAM_BOT_TOKEN: 'cms-token',
  TELEGRAM_ADMIN_IDS: '12345, 67890,12345',
  TELEGRAM_WEBHOOK_SECRET: 'safe_secret',
  TELEGRAM_LEADS_BOT_TOKEN: 'leads-token',
  TELEGRAM_LEADS_ADMIN_IDS: '24680, 13579,24680',
  CLOUDINARY_CLOUD_NAME: 'cloud',
  CLOUDINARY_API_KEY: 'key',
  CLOUDINARY_API_SECRET: 'secret',
  DATABASE_URL: 'postgresql://db.internal:5432/railway'
};

test('production requires its database and both Telegram bot configurations', () => {
  for (const variableName of [
    'DATABASE_URL',
    'TELEGRAM_BOT_TOKEN',
    'TELEGRAM_ADMIN_IDS',
    'TELEGRAM_WEBHOOK_SECRET',
    'TELEGRAM_LEADS_BOT_TOKEN',
    'TELEGRAM_LEADS_ADMIN_IDS'
  ]) {
    assert.throws(
      () => loadConfig({ ...production, [variableName]: '' }),
      new RegExp(variableName)
    );
  }
});

test('CMS and Leads Telegram settings are parsed into independent config', () => {
  const config = loadConfig(production);
  assert.deepEqual(config.telegram.cms, {
    botToken: 'cms-token',
    adminIds: ['12345', '67890'],
    webhookSecret: 'safe_secret'
  });
  assert.deepEqual(config.telegram.leads, {
    botToken: 'leads-token',
    adminIds: ['24680', '13579']
  });
  assert.equal(config.database.databaseUrl, 'postgresql://db.internal:5432/railway');
  assert.equal('google' in config, false);
});

test('malformed CMS and Leads Telegram administrator IDs are rejected', () => {
  assert.throws(
    () => loadConfig({ ...production, TELEGRAM_ADMIN_IDS: '12345,admin' }),
    /TELEGRAM_ADMIN_IDS must contain only comma-separated numeric IDs/
  );
  assert.throws(
    () => loadConfig({ ...production, TELEGRAM_LEADS_ADMIN_IDS: '24680,-1' }),
    /TELEGRAM_LEADS_ADMIN_IDS must contain only comma-separated numeric IDs/
  );
  assert.throws(
    () => loadConfig({ ...production, TELEGRAM_LEADS_ADMIN_IDS: '24680,,13579' }),
    /TELEGRAM_LEADS_ADMIN_IDS must contain only comma-separated numeric IDs/
  );
});
