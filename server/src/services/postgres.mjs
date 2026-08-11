import pg from 'pg';
import { migrations } from '../db/migrations.mjs';

const { Pool } = pg;

const NEWS_COLUMNS = new Set([
  'status', 'published_at', 'updated_at', 'archived_at', 'title', 'description',
  'media_type', 'media_url', 'cloudinary_public_id', 'instagram_url',
  'created_by_telegram_id', 'publish_request_id'
]);

const LEAD_COLUMNS = new Set([
  'created_at', 'name', 'phone', 'comment', 'source', 'status', 'request_id'
]);

function normalizeRecord(record) {
  if (!record) return record;
  return Object.fromEntries(Object.entries(record).map(([key, value]) => [
    key,
    value instanceof Date ? value.toISOString() : value
  ]));
}

function updateStatement(table, allowedColumns, id, patch) {
  const entries = Object.entries(patch).filter(([column]) => allowedColumns.has(column));
  if (!entries.length) return null;
  const assignments = entries.map(([column], index) => `${column} = $${index + 2}`);
  return {
    text: `UPDATE ${table} SET ${assignments.join(', ')} WHERE id = $1 RETURNING *`,
    values: [id, ...entries.map(([column, value]) => (
      value === '' && ['published_at', 'updated_at', 'archived_at', 'created_at'].includes(column) ? null : value
    ))]
  };
}

export class PostgresRepository {
  constructor({ pool, executor = pool }) {
    this.pool = pool;
    this.executor = executor;
  }

  static fromConfig(config) {
    const pool = new Pool({
      connectionString: config.databaseUrl,
      max: config.poolMax,
      connectionTimeoutMillis: config.connectionTimeoutMs,
      idleTimeoutMillis: config.idleTimeoutMs,
      application_name: 'bella-dent-api'
    });
    return new PostgresRepository({ pool });
  }

  async migrate() {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      await client.query("SELECT pg_advisory_xact_lock(hashtextextended('bella-dent:migrations', 0))");
      await client.query(`
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version integer PRIMARY KEY,
          name text NOT NULL,
          applied_at timestamptz NOT NULL DEFAULT now()
        )
      `);
      const applied = await client.query('SELECT version FROM schema_migrations');
      const appliedVersions = new Set(applied.rows.map((row) => Number(row.version)));
      for (const migration of migrations) {
        if (appliedVersions.has(migration.version)) continue;
        await client.query(migration.sql);
        await client.query(
          'INSERT INTO schema_migrations (version, name) VALUES ($1, $2)',
          [migration.version, migration.name]
        );
      }
      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  async transaction(lockKey, callback) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      if (lockKey) {
        await client.query('SELECT pg_advisory_xact_lock(hashtextextended($1, 0))', [lockKey]);
      }
      const repository = new PostgresRepository({ pool: this.pool, executor: client });
      const result = await callback(repository);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  async ping() {
    const result = await this.executor.query('SELECT 1 AS healthy');
    return result.rows[0]?.healthy === 1;
  }

  async close() {
    await this.pool.end();
  }

  async listNews() {
    const result = await this.executor.query(`
      SELECT * FROM news
      ORDER BY published_at DESC NULLS LAST, id DESC
    `);
    return result.rows.map(normalizeRecord);
  }

  async appendNews(record) {
    const result = await this.executor.query(`
      INSERT INTO news (
        id, status, published_at, updated_at, archived_at, title, description,
        media_type, media_url, cloudinary_public_id, instagram_url,
        created_by_telegram_id, publish_request_id
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
      RETURNING *
    `, [
      record.id, record.status, record.published_at || null, record.updated_at,
      record.archived_at || null, record.title, record.description, record.media_type,
      record.media_url, record.cloudinary_public_id, record.instagram_url || '',
      record.created_by_telegram_id, record.publish_request_id
    ]);
    return normalizeRecord(result.rows[0]);
  }

  async updateNews(id, patch) {
    const statement = updateStatement('news', NEWS_COLUMNS, id, patch);
    if (!statement) return this.findNewsById(id);
    const result = await this.executor.query(statement.text, statement.values);
    return normalizeRecord(result.rows[0] || null);
  }

  async findNewsById(id) {
    const result = await this.executor.query('SELECT * FROM news WHERE id = $1', [id]);
    return normalizeRecord(result.rows[0] || null);
  }

  async listLeads() {
    const result = await this.executor.query('SELECT * FROM leads ORDER BY created_at DESC, id DESC');
    return result.rows.map(normalizeRecord);
  }

  async appendLead(record) {
    const result = await this.executor.query(`
      INSERT INTO leads (id, created_at, name, phone, comment, source, status, request_id)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
      RETURNING *
    `, [
      record.id, record.created_at, record.name, record.phone, record.comment || '',
      record.source, record.status, record.request_id
    ]);
    return normalizeRecord(result.rows[0]);
  }

  async updateLead(id, patch) {
    const statement = updateStatement('leads', LEAD_COLUMNS, id, patch);
    if (!statement) {
      const result = await this.executor.query('SELECT * FROM leads WHERE id = $1', [id]);
      return normalizeRecord(result.rows[0] || null);
    }
    const result = await this.executor.query(statement.text, statement.values);
    return normalizeRecord(result.rows[0] || null);
  }
}
