export class FakeRepository {
  constructor({ news = [], leads = [] } = {}) {
    this.news = news.map((item, index) => ({ ...item, _rowNumber: index + 2 }));
    this.leads = leads.map((item, index) => ({ ...item, _rowNumber: index + 2 }));
    this.failAppendNews = false;
  }

  async listNews() { return this.news.map((item) => ({ ...item })); }
  async appendNews(record) {
    if (this.failAppendNews) throw new Error('Sheets append failed');
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
}

export function makeConfig() {
  return {
    allowedOrigins: new Set(['https://belladentclinik.kr.ua']),
    telegram: { webhookSecret: 'test-secret' },
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
