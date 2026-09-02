import { sanitizeText } from '../lib/sanitize.mjs';

function commandFrom(message) {
  return sanitizeText(message?.text || '').split(/\s+/, 1)[0].toLowerCase();
}

export class TelegramLeadsBot {
  constructor({ telegram, repository, adminIds = [], publicAccess = true }) {
    this.telegram = telegram;
    this.repository = repository;
    this.adminIds = new Set(adminIds.map(String));
    this.publicAccess = publicAccess;
  }

  async handleUpdate(update) {
    const message = update?.message;
    const actor = message?.from;
    const chat = message?.chat;
    if (!actor || !chat) return;

    const chatId = String(chat.id);
    const isConfiguredAdmin = this.adminIds.has(String(actor.id));
    if (!this.publicAccess && !isConfiguredAdmin) {
      await this.telegram.sendMessage(chatId, 'Ця дія недоступна.');
      return;
    }
    if (chat.type && chat.type !== 'private') {
      await this.telegram.sendMessage(chatId, 'Відкрийте бота в особистому чаті, щоб отримувати заявки.');
      return;
    }

    const command = commandFrom(message);
    if (command === '/start') {
      await this.repository.upsertLeadSubscriber({
        chatId,
        userId: String(actor.id),
        username: actor.username || '',
        firstName: actor.first_name || '',
        lastName: actor.last_name || ''
      });
      await this.telegram.sendMessage(
        chatId,
        '✅ Підписку увімкнено. Нові заявки з сайту Bella Dent надходитимуть у цей чат.\n\n/stop — вимкнути сповіщення\n/status — перевірити підписку'
      );
      return;
    }

    if (command === '/stop') {
      await this.repository.deactivateLeadSubscriber(chatId);
      await this.telegram.sendMessage(chatId, 'Сповіщення про нові заявки вимкнено. Щоб увімкнути їх знову, натисніть /start.');
      return;
    }

    if (command === '/status') {
      const subscriber = await this.repository.findLeadSubscriber(chatId);
      await this.telegram.sendMessage(
        chatId,
        subscriber?.is_active
          ? '✅ Підписка активна. Ви отримуватимете нові заявки з сайту.'
          : 'Підписка вимкнена. Натисніть /start, щоб отримувати нові заявки.'
      );
      return;
    }

    await this.telegram.sendMessage(chatId, 'Натисніть /start, щоб отримувати нові заявки з сайту Bella Dent.');
  }
}
