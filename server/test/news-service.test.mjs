import test from 'node:test';
import assert from 'node:assert/strict';
import { NewsService } from '../src/services/news-service.mjs';
import { FakeRepository, draft } from './helpers.mjs';

test('rolling publication window follows A through E acceptance sequence', async () => {
  const repository = new FakeRepository();
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
  const repository = new FakeRepository();
  const service = new NewsService({ repository, idFactory: () => 'n001' });
  const first = await service.publish(draft('A', 'same-request'));
  const second = await service.publish(draft('A', 'same-request'));
  assert.equal(first.news.id, second.news.id);
  assert.equal(second.idempotent, true);
  assert.equal((await repository.listNews()).length, 1);
});

test('restore makes archived news newest and reapplies rolling window', async () => {
  const repository = new FakeRepository();
  let id = 0;
  let tick = Date.parse('2026-08-11T09:00:00.000Z');
  const service = new NewsService({ repository, clock: () => new Date(tick++), idFactory: () => `n${++id}` });
  for (const title of ['A', 'B', 'C', 'D']) await service.publish(draft(title, `r-${title}`));
  const a = (await repository.listNews()).find((item) => item.title === 'Новина A');
  const restored = await service.restore(a.id);
  assert.deepEqual(restored.published.map((item) => item.title.at(-1)), ['A', 'D', 'C']);
  assert.equal((await repository.listNews()).find((item) => item.title === 'Новина B').status, 'archived');
});
