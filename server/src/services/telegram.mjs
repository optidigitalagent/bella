import { ExternalServiceError } from '../lib/errors.mjs';

export class TelegramClient {
  constructor(botToken, fetchImpl = fetch) {
    this.baseUrl = `https://api.telegram.org/bot${botToken}`;
    this.fileBaseUrl = `https://api.telegram.org/file/bot${botToken}`;
    this.fetch = fetchImpl;
  }

  async call(method, payload = {}) {
    try {
      const response = await this.fetch(`${this.baseUrl}/${method}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(15_000)
      });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.description || `Telegram HTTP ${response.status}`);
      return body.result;
    } catch (error) {
      throw new ExternalServiceError('telegram', `Telegram ${method} failed`, { cause: error });
    }
  }

  sendMessage(chatId, text, replyMarkup) {
    return this.call('sendMessage', {
      chat_id: chatId,
      text,
      ...(replyMarkup ? { reply_markup: replyMarkup } : {})
    });
  }

  answerCallbackQuery(callbackQueryId, text) {
    return this.call('answerCallbackQuery', {
      callback_query_id: callbackQueryId,
      ...(text ? { text } : {})
    });
  }

  getFile(fileId) {
    return this.call('getFile', { file_id: fileId });
  }

  async downloadFile(filePath, maxBytes) {
    try {
      const response = await this.fetch(`${this.fileBaseUrl}/${filePath}`, {
        signal: AbortSignal.timeout(30_000)
      });
      if (!response.ok) throw new Error(`Telegram file HTTP ${response.status}`);
      const declaredSize = Number(response.headers.get('content-length') || 0);
      if (declaredSize > maxBytes) throw new Error('Telegram file exceeds the configured size limit');
      const buffer = Buffer.from(await response.arrayBuffer());
      if (!buffer.length || buffer.length > maxBytes) throw new Error('Telegram file size is invalid');
      return buffer;
    } catch (error) {
      throw new ExternalServiceError('telegram', 'Unable to download Telegram media', { cause: error });
    }
  }

  setWebhook(url, secretToken) {
    return this.call('setWebhook', {
      url,
      secret_token: secretToken,
      allowed_updates: ['message', 'callback_query'],
      drop_pending_updates: false
    });
  }
}
