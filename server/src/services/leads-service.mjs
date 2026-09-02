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

  async recipientIds(repository = this.repository) {
    const subscribers = typeof repository.listActiveLeadSubscriberIds === 'function'
      ? await repository.listActiveLeadSubscriberIds()
      : [];
    return [...new Set([...this.adminIds, ...subscribers].map(String))];
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

      const recipientIds = await this.recipientIds(repository);
      const deliveries = await Promise.allSettled(
        recipientIds.map((recipientId) => this.telegram.sendMessage(recipientId, text))
      );
      const deliveredCount = deliveries.filter((result) => result.status === 'fulfilled').length;
      if (!deliveredCount) {
        await repository.updateLead(record.id, { status: 'notification_failed' });
        return {
          error: new ExternalServiceError(
            'telegram',
            recipientIds.length
              ? 'Lead was saved but could not be delivered to an active Telegram recipient'
              : 'Lead was saved but there are no active Telegram recipients'
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
