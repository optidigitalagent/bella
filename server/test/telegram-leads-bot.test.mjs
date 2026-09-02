import test from 'node:test';
import assert from 'node:assert/strict';
import { TelegramLeadsBot } from '../src/bot/leads-handler.mjs';
import { MemoryRepository } from './helpers.mjs';

function makeTelegram() {
  return {
    messages: [],
    async sendMessage(chatId, text) { this.messages.push({ chatId, text }); }
  };
}

function update(text, id = 7, chatType = 'private') {
  return {
    message: {
      from: { id, username: `user${id}`, first_name: 'Тест' },
      chat: { id, type: chatType },
      text
    }
  };
}

test('public user can subscribe, check status and unsubscribe', async () => {
  const repository = new MemoryRepository();
  const telegram = makeTelegram();
  const bot = new TelegramLeadsBot({ telegram, repository, publicAccess: true });

  await bot.handleUpdate(update('/start'));
  assert.deepEqual(await repository.listActiveLeadSubscriberIds(), ['7']);
  assert.match(telegram.messages.at(-1).text, /Підписку увімкнено/);

  await bot.handleUpdate(update('/status'));
  assert.match(telegram.messages.at(-1).text, /Підписка активна/);

  await bot.handleUpdate(update('/stop'));
  assert.deepEqual(await repository.listActiveLeadSubscriberIds(), []);
  assert.match(telegram.messages.at(-1).text, /вимкнено/);
});

test('lead subscriptions are limited to private chats', async () => {
  const repository = new MemoryRepository();
  const telegram = makeTelegram();
  const bot = new TelegramLeadsBot({ telegram, repository, publicAccess: true });
  await bot.handleUpdate(update('/start', 7, 'group'));
  assert.deepEqual(await repository.listActiveLeadSubscriberIds(), []);
  assert.match(telegram.messages.at(-1).text, /особистому чаті/);
});

test('restricted mode still allows configured administrators only', async () => {
  const repository = new MemoryRepository();
  const telegram = makeTelegram();
  const bot = new TelegramLeadsBot({ telegram, repository, adminIds: ['1'], publicAccess: false });
  await bot.handleUpdate(update('/start', 2));
  assert.match(telegram.messages.at(-1).text, /недоступна/);
  await bot.handleUpdate(update('/start', 1));
  assert.deepEqual(await repository.listActiveLeadSubscriberIds(), ['1']);
});
