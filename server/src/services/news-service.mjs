import { randomUUID } from 'node:crypto';
import { Mutex } from '../lib/mutex.mjs';
import { newsDraftSchema, newsPatchSchema } from '../validation.mjs';

function asMillis(value) {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function newestFirst(a, b) {
  const byDate = asMillis(b.published_at) - asMillis(a.published_at);
  if (byDate) return byDate;
  return Number(b._rowNumber || 0) - Number(a._rowNumber || 0);
}

export function toPublicNews(record) {
  return {
    id: record.id,
    title: record.title,
    description: record.description,
    mediaType: record.media_type,
    mediaUrl: record.media_url,
    instagramUrl: record.instagram_url || '',
    publishedAt: record.published_at
  };
}

export class NewsService {
  constructor({ repository, clock = () => new Date(), idFactory = () => `n_${randomUUID()}`, mutex = new Mutex() }) {
    this.repository = repository;
    this.clock = clock;
    this.idFactory = idFactory;
    this.mutex = mutex;
  }

  async getPublished() {
    const records = await this.repository.listNews();
    return records.filter((record) => record.status === 'published').sort(newestFirst).slice(0, 3).map(toPublicNews);
  }

  async getActiveInternal() {
    const records = await this.repository.listNews();
    return records.filter((record) => record.status === 'published').sort(newestFirst).slice(0, 3);
  }

  async getArchive(page = 0, pageSize = 5) {
    const records = await this.repository.listNews();
    const archived = records
      .filter((record) => record.status === 'archived')
      .sort((a, b) => asMillis(b.archived_at || b.updated_at) - asMillis(a.archived_at || a.updated_at));
    const safePage = Math.max(0, Number(page) || 0);
    const start = safePage * pageSize;
    return {
      items: archived.slice(start, start + pageSize),
      page: safePage,
      hasPrevious: safePage > 0,
      hasNext: start + pageSize < archived.length,
      total: archived.length
    };
  }

  async findById(id) {
    return (await this.repository.listNews()).find((record) => record.id === id) || null;
  }

  async publish(input) {
    const draft = newsDraftSchema.parse(input);
    return this.#transaction('news:rolling-window', async (repository) => {
      const records = await repository.listNews();
      const existing = records.find((record) => record.publish_request_id === draft.publishRequestId);
      if (existing) {
        const verification = await this.#enforceAndVerify(repository);
        return { news: toPublicNews(existing), archived: verification.archived, idempotent: true };
      }

      const timestamp = this.#nextPublishedAt(records);
      const record = {
        id: this.idFactory(),
        status: 'published',
        published_at: timestamp,
        updated_at: timestamp,
        archived_at: '',
        title: draft.title,
        description: draft.description,
        media_type: draft.mediaType,
        media_url: draft.mediaUrl,
        cloudinary_public_id: draft.cloudinaryPublicId,
        instagram_url: draft.instagramUrl,
        created_by_telegram_id: draft.createdByTelegramId,
        publish_request_id: draft.publishRequestId
      };

      await repository.appendNews(record);
      const verification = await this.#enforceAndVerify(repository, record.id);
      const publishedRecord = verification.published.find((item) => item.id === record.id);
      if (!publishedRecord) throw new Error('Newly published news did not remain in the active window');
      return { news: toPublicNews(publishedRecord), archived: verification.archived, idempotent: false };
    });
  }

  async archive(id) {
    return this.#transaction('news:rolling-window', async (repository) => {
      const current = (await repository.listNews()).find((record) => record.id === id);
      if (!current) return null;
      if (current.status === 'archived') return current;
      const now = this.clock().toISOString();
      return repository.updateNews(id, { status: 'archived', archived_at: now, updated_at: now });
    });
  }

  async restore(id) {
    return this.#transaction('news:rolling-window', async (repository) => {
      const records = await repository.listNews();
      const current = records.find((record) => record.id === id);
      if (!current) return null;
      const timestamp = this.#nextPublishedAt(records);
      await repository.updateNews(id, {
        status: 'published',
        published_at: timestamp,
        updated_at: timestamp,
        archived_at: ''
      });
      return this.#enforceAndVerify(repository, id);
    });
  }

  async update(id, input) {
    const patch = newsPatchSchema.parse(input);
    return this.#transaction(`news:edit:${id}`, async (repository) => {
      const current = (await repository.listNews()).find((record) => record.id === id);
      if (!current) return null;
      const mapped = { updated_at: this.clock().toISOString() };
      if (patch.title !== undefined) mapped.title = patch.title;
      if (patch.description !== undefined) mapped.description = patch.description;
      if (patch.instagramUrl !== undefined) mapped.instagram_url = patch.instagramUrl;
      if (patch.mediaType !== undefined) mapped.media_type = patch.mediaType;
      if (patch.mediaUrl !== undefined) mapped.media_url = patch.mediaUrl;
      if (patch.cloudinaryPublicId !== undefined) mapped.cloudinary_public_id = patch.cloudinaryPublicId;
      return repository.updateNews(id, mapped);
    });
  }

  #nextPublishedAt(records) {
    const clockMs = this.clock().getTime();
    const latestMs = records.reduce((max, record) => Math.max(max, asMillis(record.published_at)), 0);
    return new Date(Math.max(clockMs, latestMs + 1)).toISOString();
  }

  async #enforceAndVerify(repository, expectedActiveId) {
    const before = (await repository.listNews()).filter((record) => record.status === 'published').sort(newestFirst);
    const overflow = before.slice(3);
    const archivedAt = this.clock().toISOString();
    for (const record of overflow) {
      await repository.updateNews(record.id, {
        status: 'archived',
        archived_at: archivedAt,
        updated_at: archivedAt
      });
    }

    const afterAll = await repository.listNews();
    const published = afterAll.filter((record) => record.status === 'published').sort(newestFirst);
    if (published.length > 3) throw new Error('Rolling window invariant failed: more than three published news');
    const expectedIds = before.slice(0, 3).map((record) => record.id);
    const actualIds = published.map((record) => record.id);
    if (expectedIds.join('|') !== actualIds.join('|')) throw new Error('Rolling window invariant failed: published order mismatch');
    if (expectedActiveId && !published.some((record) => record.id === expectedActiveId)) {
      throw new Error('Rolling window invariant failed: expected news is not active');
    }
    return { published, archived: overflow };
  }

  async #transaction(lockKey, callback) {
    if (typeof this.repository.transaction === 'function') {
      return this.repository.transaction(lockKey, callback);
    }
    return this.mutex.runExclusive(() => callback(this.repository));
  }
}
