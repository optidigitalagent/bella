import test from 'node:test';
import assert from 'node:assert/strict';
import { LeadsService } from '../src/services/leads-service.mjs';
import { FakeRepository } from './helpers.mjs';

test('lead is only marked delivered after every Telegram admin confirms delivery', async () => {
  const repository = new FakeRepository();
  const telegram = { sendMessage: async (id) => { if (id === '2') throw new Error('delivery failed'); } };
  const service = new LeadsService({ repository, telegram, adminIds: ['1', '2'], idFactory: () => 'l1' });
  await assert.rejects(service.submit({ name: 'Анна', phone: '+380671234567', comment: '', requestId: 'lead-request' }));
  assert.equal(repository.leads[0].status, 'notification_failed');
});

test('delivered requestId is idempotent', async () => {
  const repository = new FakeRepository();
  let messages = 0;
  const telegram = { sendMessage: async () => { messages++; } };
  const service = new LeadsService({ repository, telegram, adminIds: ['1'], idFactory: () => 'l1' });
  const lead = { name: 'Анна', phone: '+380671234567', comment: '', requestId: 'lead-request' };
  await service.submit(lead);
  await service.submit(lead);
  assert.equal(messages, 1);
  assert.equal(repository.leads.length, 1);
});
