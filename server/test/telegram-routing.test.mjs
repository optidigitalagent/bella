import test from 'node:test';
import assert from 'node:assert/strict';
import { DraftStore } from '../src/bot/state.mjs';
import { createTelegramRuntime } from '../src/telegram-runtime.mjs';
import { MemoryRepository } from './helpers.mjs';

class RecordingTelegramClient {
  static instances = [];

  constructor(token) {
    this.token = token;
    this.messages = [];
    RecordingTelegramClient.instances.push(this);
  }

  async sendMessage(chatId, text, markup) {
    this.messages.push({ chatId, text, markup });
  }

  async answerCallbackQuery() {}
}

test('CMS commands and website leads use independent Telegram transports', async () => {
  RecordingTelegramClient.instances = [];
  const repository = new MemoryRepository();
  const draftStore = new DraftStore({ ttlMs: 10_000 });
  const config = {
    telegram: {
      cms: { botToken: 'cms-token', adminIds: ['100'], webhookSecret: 'secret' },
      leads: { botToken: 'leads-token', adminIds: ['200'] }
    },
    cloudinary: { maxMediaBytes: 1_000 }
  };
  const runtime = createTelegramRuntime({
    config,
    repository,
    newsService: {},
    mediaService: {},
    draftStore,
    logger: { error() {}, warn() {} },
    TelegramClientClass: RecordingTelegramClient
  });

  await runtime.telegramCms.handleUpdate({
    message: { from: { id: 100 }, chat: { id: 100 }, text: '/start' }
  });
  await runtime.leadsService.submit({
    name: 'Routing QA',
    phone: '+380000000001',
    comment: 'Two-bot transport test',
    requestId: 'routing-test'
  });

  assert.notEqual(runtime.cmsTelegram, runtime.leadsTelegram);
  assert.equal(runtime.cmsTelegram.token, 'cms-token');
  assert.equal(runtime.leadsTelegram.token, 'leads-token');
  assert.equal(runtime.cmsTelegram.messages.length, 1);
  assert.equal(runtime.cmsTelegram.messages[0].chatId, 100);
  assert.equal(runtime.cmsTelegram.messages[0].text.includes('Routing QA'), false);
  assert.equal(runtime.leadsTelegram.messages.length, 1);
  assert.equal(runtime.leadsTelegram.messages[0].chatId, '200');
  assert.equal(runtime.leadsTelegram.messages[0].text.includes('Routing QA'), true);
  assert.equal(runtime.leadsTelegram.messages[0].markup, undefined);
  assert.equal(repository.leads[0].status, 'delivered');
  draftStore.close();
});
