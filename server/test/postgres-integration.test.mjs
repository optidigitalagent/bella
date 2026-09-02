import { randomUUID } from 'node:crypto';
import test from 'node:test';
import assert from 'node:assert/strict';
import pg from 'pg';
import { PostgresRepository } from '../src/services/postgres.mjs';
import { NewsService } from '../src/services/news-service.mjs';
import { LeadsService } from '../src/services/leads-service.mjs';
import { draft } from './helpers.mjs';

const { Pool } = pg;
const testDatabaseUrl = process.env.TEST_DATABASE_URL;

test('PostgreSQL migrations, repositories, transactions, and concurrency', {
  skip: !testDatabaseUrl && 'TEST_DATABASE_URL is not set'
}, async () => {
  const schema = `bella_test_${randomUUID().replaceAll('-', '')}`;
  assert.match(schema, /^bella_test_[a-f0-9]{32}$/);
  const adminPool = new Pool({ connectionString: testDatabaseUrl, max: 2 });
  let repository;

  try {
    await adminPool.query(`CREATE SCHEMA ${schema}`);
    const pool = new Pool({
      connectionString: testDatabaseUrl,
      max: 8,
      options: `-c search_path=${schema}`
    });
    repository = new PostgresRepository({ pool });

    await repository.migrate();
    await repository.migrate();
    assert.equal((await pool.query('SELECT count(*)::int AS count FROM schema_migrations')).rows[0].count, 2);
    const tables = await pool.query(`
      SELECT table_name FROM information_schema.tables
      WHERE table_schema = $1 AND table_name IN ('news', 'leads', 'telegram_lead_subscribers')
      ORDER BY table_name
    `, [schema]);
    assert.deepEqual(
      tables.rows.map((row) => row.table_name),
      ['leads', 'news', 'telegram_lead_subscribers']
    );

    await repository.upsertLeadSubscriber({
      chatId: '2', userId: '2', username: 'bella_admin', firstName: 'Bella', lastName: 'Admin'
    });
    assert.deepEqual(await repository.listActiveLeadSubscriberIds(), ['2']);
    assert.equal((await repository.findLeadSubscriber('2')).username, 'bella_admin');
    await repository.deactivateLeadSubscriber('2');
    assert.deepEqual(await repository.listActiveLeadSubscriberIds(), []);
    await repository.upsertLeadSubscriber({ chatId: '2', userId: '2', firstName: 'Bella' });

    let id = 0;
    let tick = Date.parse('2026-08-11T08:00:00.000Z');
    const serviceA = new NewsService({
      repository,
      clock: () => new Date(tick++),
      idFactory: () => `news_${++id}`
    });
    const serviceB = new NewsService({
      repository,
      clock: () => new Date(tick++),
      idFactory: () => `news_${++id}`
    });

    const duplicate = await Promise.all([
      serviceA.publish(draft('A', 'db-duplicate')),
      serviceB.publish(draft('A', 'db-duplicate'))
    ]);
    assert.equal(new Set(duplicate.map((result) => result.news.id)).size, 1);
    assert.equal((await repository.listNews()).length, 1);

    for (const title of ['B', 'C', 'D', 'E']) {
      await serviceA.publish(draft(title, `db-${title}`));
    }
    assert.deepEqual((await serviceA.getPublished()).map((item) => item.title.at(-1)), ['E', 'D', 'C']);
    const records = await repository.listNews();
    assert.equal(records.find((record) => record.title.endsWith('A')).status, 'archived');
    assert.equal(records.find((record) => record.title.endsWith('B')).status, 'archived');

    const c = records.find((record) => record.title.endsWith('C'));
    await serviceA.update(c.id, { title: 'Оновлена новина C' });
    assert.equal((await serviceA.findById(c.id)).title, 'Оновлена новина C');
    await serviceA.archive(c.id);
    assert.equal((await serviceA.findById(c.id)).status, 'archived');
    const restored = await serviceA.restore(c.id);
    assert.equal(restored.published[0].id, c.id);
    assert.equal(restored.published.length, 3);

    const rollbackId = 'news_rollback';
    await assert.rejects(repository.transaction('integration:rollback', async (transaction) => {
      await transaction.appendNews({
        id: rollbackId,
        status: 'published',
        published_at: new Date(tick++).toISOString(),
        updated_at: new Date(tick++).toISOString(),
        archived_at: '',
        title: 'Rollback',
        description: 'Rollback transaction record',
        media_type: 'image',
        media_url: 'https://res.cloudinary.com/demo/image/upload/rollback.jpg',
        cloudinary_public_id: 'bella-dent/news/rollback',
        instagram_url: '',
        created_by_telegram_id: '12345',
        publish_request_id: 'rollback-request'
      });
      throw new Error('force rollback');
    }), /force rollback/);
    assert.equal((await repository.listNews()).some((record) => record.id === rollbackId), false);

    let messages = 0;
    let leadId = 0;
    const telegram = { sendMessage: async () => { messages++; } };
    const leadsA = new LeadsService({ repository, telegram, adminIds: ['1'], idFactory: () => `lead_${++leadId}` });
    const leadsB = new LeadsService({ repository, telegram, adminIds: ['1'], idFactory: () => `lead_${++leadId}` });
    const lead = { name: 'Анна', phone: '+380671234567', comment: '', requestId: 'db-lead-request' };
    const leadResults = await Promise.all([leadsA.submit(lead), leadsB.submit(lead)]);
    assert.equal(messages, 2);
    assert.equal(new Set(leadResults.map((result) => result.id)).size, 1);
    assert.equal((await repository.listLeads()).length, 1);
    assert.equal((await repository.listLeads())[0].status, 'delivered');
  } finally {
    if (repository) await repository.close();
    await adminPool.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`);
    await adminPool.end();
  }
});
