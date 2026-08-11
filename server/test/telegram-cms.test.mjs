import test from 'node:test';
import assert from 'node:assert/strict';
import { TelegramCms } from '../src/bot/handlers.mjs';
import { DraftStore } from '../src/bot/state.mjs';

function makeTelegram() {
  return {
    messages: [],
    async sendMessage(chatId, text, markup) { this.messages.push({ chatId, text, markup }); },
    async answerCallbackQuery() {},
    async getFile() { return { file_path: 'photo.jpg', file_size: 100 }; },
    async downloadFile() { return Buffer.from([0xff, 0xd8, 0xff, 0x00]); }
  };
}

function update(text, userId = 1) {
  return { message: { from: { id: userId }, chat: { id: userId }, text } };
}

test('unauthorized Telegram ID has no CMS access', async () => {
  const telegram = makeTelegram();
  let newsCalls = 0;
  const store = new DraftStore({ ttlMs: 10_000 });
  const cms = new TelegramCms({
    telegram,
    newsService: { getActiveInternal: async () => { newsCalls++; return []; } },
    mediaService: {}, draftStore: store, adminIds: ['1'], maxMediaBytes: 1000,
    logger: { error() {}, warn() {} }
  });
  await cms.handleUpdate(update('📰 Активні новини', 999));
  assert.equal(newsCalls, 0);
  assert.equal(telegram.messages.at(-1).text, 'Ця дія недоступна.');
  store.close();
});

test('Cloudinary upload error does not create published news', async () => {
  const telegram = makeTelegram();
  let published = 0;
  const store = new DraftStore({ ttlMs: 10_000 });
  const cms = new TelegramCms({
    telegram,
    newsService: { publish: async () => { published++; } },
    mediaService: { upload: async () => { throw new Error('cloudinary failed'); } },
    draftStore: store, adminIds: ['1'], maxMediaBytes: 1000,
    logger: { error() {}, warn() {} }
  });
  await cms.handleUpdate(update('➕ Додати новину'));
  await cms.handleUpdate(update('Заголовок'));
  await cms.handleUpdate(update('Достатньо довгий опис'));
  await cms.handleUpdate({ message: { from: { id: 1 }, chat: { id: 1 }, photo: [{ file_id: 'photo', file_size: 100 }] } });
  assert.equal(published, 0);
  assert.match(telegram.messages.at(-1).text, /Не вдалося обробити медіа/);
  store.close();
});

test('database publish error never sends Telegram success', async () => {
  const telegram = makeTelegram();
  const store = new DraftStore({ ttlMs: 10_000 });
  const cms = new TelegramCms({
    telegram,
    newsService: { publish: async () => { throw new Error('Database failed'); } },
    mediaService: { upload: async () => ({ mediaType: 'image', mediaUrl: 'https://res.cloudinary.com/demo/image/upload/a.jpg', cloudinaryPublicId: 'a' }) },
    draftStore: store, adminIds: ['1'], maxMediaBytes: 1000,
    logger: { error() {}, warn() {} }
  });
  await cms.handleUpdate(update('➕ Додати новину'));
  await cms.handleUpdate(update('Заголовок'));
  await cms.handleUpdate(update('Достатньо довгий опис'));
  await cms.handleUpdate({ message: { from: { id: 1 }, chat: { id: 1 }, photo: [{ file_id: 'photo', file_size: 100 }] } });
  await cms.handleUpdate(update('Пропустити'));
  await cms.handleUpdate({ callback_query: { id: 'publish-request', from: { id: 1 }, message: { chat: { id: 1 } }, data: 'publish' } });
  assert.equal(telegram.messages.some((message) => message.text.includes('✅ Новину опубліковано')), false);
  assert.match(telegram.messages.at(-1).text, /Публікація не завершена/);
  store.close();
});
