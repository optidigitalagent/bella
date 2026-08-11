import { randomUUID } from 'node:crypto';
import { ExternalServiceError } from '../lib/errors.mjs';

export class LeadsService {
  constructor({ repository, telegram, adminIds, clock = () => new Date(), idFactory = () => `l_${randomUUID()}` }) {
    this.repository = repository;
    this.telegram = telegram;
    this.adminIds = adminIds;
    this.clock = clock;
    this.idFactory = idFactory;
  }

  async submit(lead) {
    const requestId = lead.requestId || randomUUID();
    const operation = async (repository) => {
      const existing = (await repository.listLeads()).find((record) => record.request_id === requestId);
      if (existing?.status === 'delivered') return { result: { id: existing.id, duplicate: true } };

      const record = existing || {
        id: this.idFactory(),
        created_at: this.clock().toISOString(),
        name: lead.name,
        phone: lead.phone,
        comment: lead.comment,
        source: 'website',
        status: 'received',
        request_id: requestId
      };
      if (!existing) await repository.appendLead(record);

      const text = [
        '🔔 НОВА ЗАЯВКА З САЙТУ',
        '',
        'Імʼя:', lead.name,
        '',
        'Телефон:', lead.phone,
        '',
        'Коментар:', lead.comment || '—',
        '',
        'Дата:', record.created_at
      ].join('\n');

      const deliveries = await Promise.allSettled(
        this.adminIds.map((adminId) => this.telegram.sendMessage(adminId, text))
      );
      if (deliveries.some((result) => result.status === 'rejected')) {
        await repository.updateLead(record.id, { status: 'notification_failed' });
        return {
          error: new ExternalServiceError(
            'telegram',
            'Lead was saved but could not be delivered to every configured administrator'
          )
        };
      }

      await repository.updateLead(record.id, { status: 'delivered' });
      return { result: { id: record.id, duplicate: Boolean(existing) } };
    };

    const outcome = typeof this.repository.transaction === 'function'
      ? await this.repository.transaction(`lead:${requestId}`, operation)
      : await operation(this.repository);
    if (outcome.error) throw outcome.error;
    return outcome.result;
  }
}
