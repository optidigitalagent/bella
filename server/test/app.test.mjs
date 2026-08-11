import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.mjs';
import { ExternalServiceError } from '../src/lib/errors.mjs';
import { makeConfig, withServer } from './helpers.mjs';

function fixture(overrides = {}) {
  let leadCalls = 0;
  const newsService = overrides.newsService || {
    getPublished: async () => [{
      id: 'n3', title: 'C', description: 'desc', mediaType: 'image',
      mediaUrl: 'https://res.cloudinary.com/demo/image/upload/c.jpg', instagramUrl: '', publishedAt: '2026-08-11T03:00:00.000Z'
    }]
  };
  const leadsService = overrides.leadsService || { submit: async () => { leadCalls++; return { id: 'l1' }; } };
  const app = createApp({
    config: makeConfig(),
    newsService,
    leadsService,
    telegramCms: overrides.telegramCms || { handleUpdate: async () => {} },
    logger: { error() {} }
  });
  return { app, getLeadCalls: () => leadCalls };
}

test('GET /api/news returns safe public fields and no-store', async () => {
  const { app } = fixture();
  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/news`, { headers: { Origin: 'https://belladentclinik.kr.ua' } });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    assert.equal(response.headers.get('access-control-allow-origin'), 'https://belladentclinik.kr.ua');
    const body = await response.json();
    assert.deepEqual(Object.keys(body[0]).sort(), ['description', 'id', 'instagramUrl', 'mediaType', 'mediaUrl', 'publishedAt', 'title'].sort());
    assert.equal('cloudinary_public_id' in body[0], false);
  });
});

test('lead validation and honeypot do not call delivery service', async () => {
  const { app, getLeadCalls } = fixture();
  await withServer(app, async (base) => {
    const missingPhone = await fetch(`${base}/api/leads`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'Анна', website: '' }) });
    assert.equal(missingPhone.status, 400);
    const honeypot = await fetch(`${base}/api/leads`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'Анна', phone: '+380671234567', website: 'spam.example' }) });
    assert.equal(honeypot.status, 204);
    assert.equal(getLeadCalls(), 0);
  });
});

test('Telegram delivery failure cannot produce frontend success', async () => {
  const { app } = fixture({ leadsService: { submit: async () => { throw new ExternalServiceError('telegram', 'failed'); } } });
  await withServer(app, async (base) => {
    const response = await fetch(`${base}/api/leads`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ name: 'Анна', phone: '+380671234567', comment: '', website: '', requestId: 'request-123' })
    });
    assert.equal(response.status, 502);
    assert.equal((await response.json()).error, 'UPSTREAM_ERROR');
  });
});

test('webhook requires exact Telegram secret token', async () => {
  let handled = 0;
  const { app } = fixture({ telegramCms: { handleUpdate: async () => { handled++; } } });
  await withServer(app, async (base) => {
    const unauthorized = await fetch(`${base}/api/telegram/webhook`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
    assert.equal(unauthorized.status, 401);
    const authorized = await fetch(`${base}/api/telegram/webhook`, { method: 'POST', headers: { 'content-type': 'application/json', 'x-telegram-bot-api-secret-token': 'test-secret' }, body: '{}' });
    assert.equal(authorized.status, 200);
    assert.equal(handled, 1);
  });
});
