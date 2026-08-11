import test from 'node:test';
import assert from 'node:assert/strict';
import { NewsService } from '../src/services/news-service.mjs';
import { MemoryRepository, draft } from './helpers.mjs';

test('rolling publication window follows A through E acceptance sequence', async () => {
  const repository = new MemoryRepository();
  let tick = Date.parse('2026-08-11T08:00:00.000Z');
  let id = 0;
  const service = new NewsService({
    repository,
    clock: () => new Date(tick++),
    idFactory: () => `n00${++id}`
  });

  const expected = [
    ['A'],
    ['B', 'A'],
    ['C', 'B', 'A'],
    ['D', 'C', 'B'],
    ['E', 'D', 'C']
  ];
  for (let index = 0; index < expected.length; index++) {
    const title = String.fromCharCode(65 + index);
    await service.publish(draft(title, `request-${title}`));
    assert.deepEqual((await service.getPublished()).map((item) => item.title.at(-1)), expected[index]);
  }

  const records = await repository.listNews();
  assert.equal(records.find((item) => item.title === 'Новина A').status, 'archived');
  assert.equal(records.find((item) => item.title === 'Новина B').status, 'archived');
  assert.deepEqual(records.filter((item) => item.status === 'published').sort((a, b) => Date.parse(b.published_at) - Date.parse(a.published_at)).map((item) => item.title.at(-1)), ['E', 'D', 'C']);
});

test('publish_request_id is idempotent', async () => {
  const repository = new MemoryRepository();
  const service = new NewsService({ repository, idFactory: () => 'n001' });
  const first = await service.publish(draft('A', 'same-request'));
  const second = await service.publish(draft('A', 'same-request'));
  assert.equal(first.news.id, second.news.id);
  assert.equal(second.idempotent, true);
  assert.equal((await repository.listNews()).length, 1);
});

test('concurrent duplicate publish_request_id creates one record', async () => {
  const repository = new MemoryRepository();
  let id = 0;
  const firstService = new NewsService({ repository, idFactory: () => `n${++id}` });
  const secondService = new NewsService({ repository, idFactory: () => `n${++id}` });
  const results = await Promise.all([
    firstService.publish(draft('A', 'concurrent-request')),
    secondService.publish(draft('A', 'concurrent-request'))
  ]);
  assert.equal(new Set(results.map((result) => result.news.id)).size, 1);
  assert.equal(results.filter((result) => result.idempotent).length, 1);
  assert.equal((await repository.listNews()).length, 1);
});

test('restore makes archived news newest and reapplies rolling window', async () => {
  const repository = new MemoryRepository();
  let id = 0;
  let tick = Date.parse('2026-08-11T09:00:00.000Z');
  const service = new NewsService({ repository, clock: () => new Date(tick++), idFactory: () => `n${++id}` });
  for (const title of ['A', 'B', 'C', 'D']) await service.publish(draft(title, `r-${title}`));
  const a = (await repository.listNews()).find((item) => item.title === 'Новина A');
  const restored = await service.restore(a.id);
  assert.deepEqual(restored.published.map((item) => item.title.at(-1)), ['A', 'D', 'C']);
  assert.equal((await repository.listNews()).find((item) => item.title === 'Новина B').status, 'archived');
});

test('archive and edit persist all supported fields', async () => {
  const repository = new MemoryRepository();
  const service = new NewsService({ repository, idFactory: () => 'n1' });
  await service.publish(draft('A', 'edit-request'));
  await service.update('n1', {
    title: 'Оновлений заголовок',
    description: 'Оновлений достатньо довгий опис',
    instagramUrl: 'https://www.instagram.com/p/example'
  });
  const edited = await service.findById('n1');
  assert.equal(edited.title, 'Оновлений заголовок');
  assert.equal(edited.instagram_url, 'https://www.instagram.com/p/example');
  const archived = await service.archive('n1');
  assert.equal(archived.status, 'archived');
  assert.ok(archived.archived_at);
});

test('publication transaction rolls back both insert and rolling archive on failure', async () => {
  const repository = new MemoryRepository();
  let id = 0;
  const service = new NewsService({ repository, idFactory: () => `n${++id}` });
  for (const title of ['A', 'B', 'C']) await service.publish(draft(title, `r-${title}`));
  const originalUpdate = repository.updateNews.bind(repository);
  repository.updateNews = async (recordId, patch) => {
    if (patch.status === 'archived') throw new Error('forced archive failure');
    return originalUpdate(recordId, patch);
  };
  await assert.rejects(service.publish(draft('D', 'r-D')), /forced archive failure/);
  const records = await repository.listNews();
  assert.equal(records.length, 3);
  assert.deepEqual(records.map((record) => record.title.at(-1)).sort(), ['A', 'B', 'C']);
});
