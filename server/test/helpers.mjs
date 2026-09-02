export class MemoryRepository {
  constructor({ news = [], leads = [], leadSubscribers = [] } = {}) {
    this.news = news.map((item, index) => ({ ...item, _rowNumber: index + 2 }));
    this.leads = leads.map((item, index) => ({ ...item, _rowNumber: index + 2 }));
    this.leadSubscribers = leadSubscribers.map((item) => ({ ...item }));
    this.failAppendNews = false;
    this.transactionQueue = Promise.resolve();
  }

  async transaction(_lockKey, callback) {
    const previous = this.transactionQueue;
    let release;
    this.transactionQueue = new Promise((resolve) => { release = resolve; });
    await previous;
    const newsSnapshot = structuredClone(this.news);
    const leadsSnapshot = structuredClone(this.leads);
    const subscribersSnapshot = structuredClone(this.leadSubscribers);
    try {
      return await callback(this);
    } catch (error) {
      this.news = newsSnapshot;
      this.leads = leadsSnapshot;
      this.leadSubscribers = subscribersSnapshot;
      throw error;
    } finally {
      release();
    }
  }

  async listNews() { return this.news.map((item) => ({ ...item })); }
  async appendNews(record) {
    if (this.failAppendNews) throw new Error('Database insert failed');
    this.news.push({ ...record, _rowNumber: this.news.length + 2 });
    return record;
  }
  async updateNews(id, patch) {
    const index = this.news.findIndex((item) => item.id === id);
    if (index < 0) return null;
    this.news[index] = { ...this.news[index], ...patch };
    return { ...this.news[index] };
  }
  async listLeads() { return this.leads.map((item) => ({ ...item })); }
  async appendLead(record) {
    this.leads.push({ ...record, _rowNumber: this.leads.length + 2 });
    return record;
  }
  async updateLead(id, patch) {
    const index = this.leads.findIndex((item) => item.id === id);
    if (index < 0) return null;
    this.leads[index] = { ...this.leads[index], ...patch };
    return { ...this.leads[index] };
  }
  async upsertLeadSubscriber(subscriber) {
    const index = this.leadSubscribers.findIndex((item) => item.chat_id === String(subscriber.chatId));
    const record = {
      chat_id: String(subscriber.chatId), user_id: String(subscriber.userId),
      username: subscriber.username || '', first_name: subscriber.firstName || '',
      last_name: subscriber.lastName || '', is_active: true
    };
    if (index < 0) this.leadSubscribers.push(record);
    else this.leadSubscribers[index] = { ...this.leadSubscribers[index], ...record };
    return { ...record };
  }
  async deactivateLeadSubscriber(chatId) {
    const subscriber = this.leadSubscribers.find((item) => item.chat_id === String(chatId));
    if (!subscriber) return null;
    subscriber.is_active = false;
    return { ...subscriber };
  }
  async findLeadSubscriber(chatId) {
    const subscriber = this.leadSubscribers.find((item) => item.chat_id === String(chatId));
    return subscriber ? { ...subscriber } : null;
  }
  async listActiveLeadSubscriberIds() {
    return this.leadSubscribers.filter((item) => item.is_active).map((item) => item.chat_id);
  }
}

export function makeConfig() {
  return {
    allowedOrigins: new Set(['https://belladentclinik.kr.ua']),
    telegram: {
      cms: { webhookSecret: 'test-secret' },
      leads: { webhookSecret: 'leads-test-secret' }
    },
    rateLimits: { leadWindowMs: 60_000, leadMax: 100, webhookWindowMs: 60_000, webhookMax: 100 }
  };
}

export async function withServer(app, callback) {
  const server = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  const address = server.address();
  try {
    return await callback(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

export function draft(title, requestId) {
  return {
    title: `Новина ${title}`,
    description: `Опис новини ${title}`,
    mediaType: 'image',
    mediaUrl: `https://res.cloudinary.com/demo/image/upload/${title}.jpg`,
    cloudinaryPublicId: `bella-dent/news/${title}`,
    instagramUrl: '',
    createdByTelegramId: '12345',
    publishRequestId: requestId
  };
}
