import test from 'node:test';
import assert from 'node:assert/strict';
import { LeadsService } from '../src/services/leads-service.mjs';
import { MemoryRepository } from './helpers.mjs';

test('lead is only marked delivered after every Telegram admin confirms delivery', async () => {
  const repository = new MemoryRepository();
  const telegram = { sendMessage: async (id) => { if (id === '2') throw new Error('delivery failed'); } };
  const service = new LeadsService({ repository, telegram, adminIds: ['1', '2'], idFactory: () => 'l1' });
  await assert.rejects(service.submit({ name: 'Анна', phone: '+380671234567', comment: '', requestId: 'lead-request' }));
  assert.equal(repository.leads[0].status, 'notification_failed');
});

test('delivered requestId is idempotent', async () => {
  const repository = new MemoryRepository();
  let messages = 0;
  const telegram = { sendMessage: async () => { messages++; } };
  const service = new LeadsService({ repository, telegram, adminIds: ['1'], idFactory: () => 'l1' });
  const lead = { name: 'Анна', phone: '+380671234567', comment: '', requestId: 'lead-request' };
  await service.submit(lead);
  await service.submit(lead);
  assert.equal(messages, 1);
  assert.equal(repository.leads.length, 1);
});

test('concurrent duplicate requestId is stored and delivered once', async () => {
  const repository = new MemoryRepository();
  let messages = 0;
  const telegram = { sendMessage: async () => { messages++; } };
  let id = 0;
  const firstService = new LeadsService({ repository, telegram, adminIds: ['1'], idFactory: () => `l${++id}` });
  const secondService = new LeadsService({ repository, telegram, adminIds: ['1'], idFactory: () => `l${++id}` });
  const lead = { name: 'Анна', phone: '+380671234567', comment: '', requestId: 'concurrent-lead' };
  const results = await Promise.all([firstService.submit(lead), secondService.submit(lead)]);
  assert.equal(messages, 1);
  assert.equal(repository.leads.length, 1);
  assert.equal(new Set(results.map((result) => result.id)).size, 1);
});
