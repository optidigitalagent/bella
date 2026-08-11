import { BotState } from './state.mjs';
import { allowedDocumentMimeTypes, instagramUrlSchema, validateMediaBuffer, validateMediaDescriptor } from '../validation.mjs';
import { sanitizeText } from '../lib/sanitize.mjs';

const MENU = Object.freeze({
  ADD: '➕ Додати новину',
  ACTIVE: '📰 Активні новини',
  ARCHIVE: '📁 Архів',
  SKIP: 'Пропустити',
  CANCEL: '❌ Скасувати'
});

const mainKeyboard = {
  keyboard: [[{ text: MENU.ADD }], [{ text: MENU.ACTIVE }, { text: MENU.ARCHIVE }]],
  resize_keyboard: true,
  is_persistent: true
};

const instagramKeyboard = {
  keyboard: [[{ text: MENU.SKIP }], [{ text: MENU.CANCEL }]],
  resize_keyboard: true,
  one_time_keyboard: true
};

function inlineKeyboard(rows) {
  return { inline_keyboard: rows };
}

function previewText(draft) {
  return [
    'Перевірте новину:',
    '',
    'Заголовок:', draft.title,
    '',
    'Опис:', draft.description,
    '',
    'Медіа:', '✅ завантажено',
    '',
    'Instagram:', draft.instagramUrl ? '✅ додано' : '—'
  ].join('\n');
}

function summarize(record) {
  return [record.title, '', record.description, '', `Статус: ${record.status}`, `Дата: ${record.published_at || '—'}`, `Instagram: ${record.instagram_url || '—'}`].join('\n');
}

function mediaFromMessage(message) {
  if (Array.isArray(message.photo) && message.photo.length) {
    const photo = message.photo.at(-1);
    return { fileId: photo.file_id, fileSize: Number(photo.file_size || 0), mediaType: 'image' };
  }
  if (message.video) {
    return { fileId: message.video.file_id, fileSize: Number(message.video.file_size || 0), mediaType: 'video' };
  }
  if (message.document) {
    const mediaType = allowedDocumentMimeTypes.get(String(message.document.mime_type || '').toLowerCase());
    if (!mediaType) return null;
    return { fileId: message.document.file_id, fileSize: Number(message.document.file_size || 0), mediaType };
  }
  return null;
}

export class TelegramCms {
  constructor({ telegram, newsService, mediaService, draftStore, adminIds, maxMediaBytes, logger }) {
    this.telegram = telegram;
    this.newsService = newsService;
    this.mediaService = mediaService;
    this.draftStore = draftStore;
    this.adminIds = new Set(adminIds.map(String));
    this.maxMediaBytes = maxMediaBytes;
    this.logger = logger;
  }

  isAuthorized(userId) {
    return this.adminIds.has(String(userId));
  }

  async handleUpdate(update) {
    const actor = update.callback_query?.from || update.message?.from;
    const chatId = update.callback_query?.message?.chat?.id || update.message?.chat?.id;
    if (!actor || !chatId) return;
    if (!this.isAuthorized(actor.id)) {
      if (update.callback_query) await this.#safeAnswer(update.callback_query.id);
      await this.telegram.sendMessage(chatId, 'Ця дія недоступна.');
      return;
    }
    if (update.callback_query) return this.#handleCallback(update.callback_query, chatId, String(actor.id));
    return this.#handleMessage(update.message, chatId, String(actor.id));
  }

  async #handleMessage(message, chatId, userId) {
    const text = sanitizeText(message.text || '');

    if (text === '/start') {
      await this.telegram.sendMessage(chatId, 'Bella Dent — управління сайтом', mainKeyboard);
      return;
    }
    if (text === '/cancel' || text === MENU.CANCEL) {
      await this.#cancel(userId);
      await this.telegram.sendMessage(chatId, 'Дію скасовано.', mainKeyboard);
      return;
    }
    if (text === MENU.ADD) {
      await this.#cancel(userId);
      this.draftStore.set(userId, { state: BotState.WAITING_TITLE, mode: 'create', draft: {} });
      await this.telegram.sendMessage(chatId, 'Надішліть заголовок новини.');
      return;
    }
    if (text === MENU.ACTIVE) {
      await this.#showActive(chatId);
      return;
    }
    if (text === MENU.ARCHIVE) {
      await this.#showArchive(chatId, 0);
      return;
    }

    const session = this.draftStore.get(userId);
    if (!session) {
      await this.telegram.sendMessage(chatId, 'Оберіть дію в меню.', mainKeyboard);
      return;
    }

    if (session.state === BotState.WAITING_TITLE) {
      const title = sanitizeText(text);
      if (title.length < 3 || title.length > 120) {
        await this.telegram.sendMessage(chatId, 'Заголовок має містити від 3 до 120 символів. Спробуйте ще раз.');
        return;
      }
      session.draft.title = title;
      session.state = BotState.WAITING_DESCRIPTION;
      this.draftStore.set(userId, session);
      await this.telegram.sendMessage(chatId, 'Тепер надішліть опис новини.');
      return;
    }

    if (session.state === BotState.WAITING_DESCRIPTION) {
      const description = sanitizeText(text);
      if (description.length < 3 || description.length > 1500) {
        await this.telegram.sendMessage(chatId, 'Опис має містити від 3 до 1500 символів. Спробуйте ще раз.');
        return;
      }
      session.draft.description = description;
      session.state = BotState.WAITING_MEDIA;
      this.draftStore.set(userId, session);
      await this.telegram.sendMessage(chatId, 'Надішліть фотографію або відео.');
      return;
    }

    if (session.state === BotState.WAITING_MEDIA || session.state === BotState.WAITING_EDIT_MEDIA) {
      const descriptor = mediaFromMessage(message);
      if (!descriptor) {
        await this.telegram.sendMessage(chatId, 'Надішліть підтримуване фото або відео, не довільний файл.');
        return;
      }
      await this.#handleMedia(chatId, userId, session, descriptor);
      return;
    }

    if (session.state === BotState.WAITING_INSTAGRAM) {
      let instagramUrl = '';
      if (text !== MENU.SKIP) {
        const parsed = instagramUrlSchema.safeParse(text);
        if (!parsed.success) {
          await this.telegram.sendMessage(chatId, 'Надішліть коректне HTTPS-посилання Instagram або натисніть «Пропустити».', instagramKeyboard);
          return;
        }
        instagramUrl = parsed.data;
      }
      session.draft.instagramUrl = instagramUrl;
      session.state = BotState.WAITING_CONFIRMATION;
      this.draftStore.set(userId, session);
      await this.#showPreview(chatId, session.draft);
      return;
    }

    if (session.state === BotState.WAITING_EDIT_VALUE) {
      await this.#saveEditValue(chatId, userId, session, text);
      return;
    }

    await this.telegram.sendMessage(chatId, 'Скористайтеся кнопками під повідомленням або скасуйте дію.');
  }

  async #handleCallback(callback, chatId, userId) {
    await this.#safeAnswer(callback.id);
    const data = String(callback.data || '');
    if (data === 'publish') return this.#publish(chatId, userId, callback.id);
    if (data === 'draft:cancel') {
      await this.#cancel(userId);
      await this.telegram.sendMessage(chatId, 'Чернетку видалено.', mainKeyboard);
      return;
    }
    if (data === 'draft:edit') {
      await this.telegram.sendMessage(chatId, 'Що змінити?', inlineKeyboard([
        [{ text: 'Заголовок', callback_data: 'draftfield:title' }, { text: 'Опис', callback_data: 'draftfield:description' }],
        [{ text: 'Instagram', callback_data: 'draftfield:instagramUrl' }, { text: 'Медіа', callback_data: 'draftfield:media' }]
      ]));
      return;
    }
    if (data.startsWith('draftfield:')) return this.#beginDraftEdit(chatId, userId, data.slice('draftfield:'.length));
    if (data === 'active:list') return this.#showActive(chatId);
    if (data.startsWith('news:')) return this.#showNews(chatId, data.slice(5));
    if (data.startsWith('edit:')) return this.#showEditMenu(chatId, data.slice(5));
    if (data.startsWith('editfield:')) {
      const [, field, ...idParts] = data.split(':');
      return this.#beginPublishedEdit(chatId, userId, idParts.join(':'), field);
    }
    if (data.startsWith('archive:')) return this.#archive(chatId, data.slice(8));
    if (data.startsWith('restore:')) return this.#restore(chatId, data.slice(8));
    if (data.startsWith('archivepage:')) return this.#showArchive(chatId, Number(data.slice(12)) || 0);
    if (data.startsWith('archived:')) return this.#showArchivedNews(chatId, data.slice(9));
  }

  async #upload(descriptor) {
    if (descriptor.fileSize > this.maxMediaBytes) validateMediaDescriptor(descriptor, this.maxMediaBytes);
    const file = await this.telegram.getFile(descriptor.fileId);
    const confirmed = { ...descriptor, fileSize: Number(file.file_size || descriptor.fileSize) };
    validateMediaDescriptor(confirmed, this.maxMediaBytes);
    const buffer = await this.telegram.downloadFile(file.file_path, this.maxMediaBytes);
    validateMediaBuffer(buffer, descriptor.mediaType);
    return this.mediaService.upload(buffer, descriptor.mediaType);
  }

  async #handleMedia(chatId, userId, session, descriptor) {
    let uploaded;
    try {
      uploaded = await this.#upload(descriptor);
    } catch (error) {
      this.logger.error('Telegram media processing failed', error, { userId });
      await this.telegram.sendMessage(chatId, 'Не вдалося обробити медіа. Перевірте формат/розмір і спробуйте ще раз.');
      return;
    }

    if (session.state === BotState.WAITING_MEDIA) {
      session.draft = { ...session.draft, ...uploaded };
      session.state = BotState.WAITING_INSTAGRAM;
      this.draftStore.set(userId, session);
      await this.telegram.sendMessage(chatId, 'Надішліть посилання на Instagram-публікацію або натисніть «Пропустити».', instagramKeyboard);
      return;
    }

    if (session.editScope === 'draft') {
      const oldMedia = {
        publicId: session.draft.cloudinaryPublicId,
        mediaType: session.draft.mediaType
      };
      session.draft = { ...session.draft, ...uploaded };
      session.state = BotState.WAITING_CONFIRMATION;
      delete session.editField;
      delete session.editScope;
      this.draftStore.set(userId, session);
      await this.#removeQuietly(oldMedia.publicId, oldMedia.mediaType);
      await this.#showPreview(chatId, session.draft);
      return;
    }

    const current = await this.newsService.findById(session.targetId);
    if (!current) {
      await this.#removeQuietly(uploaded.cloudinaryPublicId, uploaded.mediaType);
      this.draftStore.delete(userId);
      await this.telegram.sendMessage(chatId, 'Новину не знайдено.', mainKeyboard);
      return;
    }
    try {
      await this.newsService.update(session.targetId, uploaded);
    } catch (error) {
      await this.#removeQuietly(uploaded.cloudinaryPublicId, uploaded.mediaType);
      throw error;
    }
    this.draftStore.delete(userId);
    await this.#removeQuietly(current.cloudinary_public_id, current.media_type);
    await this.telegram.sendMessage(chatId, '✅ Медіа оновлено.', mainKeyboard);
  }

  async #showPreview(chatId, draft) {
    await this.telegram.sendMessage(chatId, previewText(draft), inlineKeyboard([
      [{ text: '✅ Опублікувати', callback_data: 'publish' }],
      [{ text: '✏️ Змінити', callback_data: 'draft:edit' }, { text: '❌ Скасувати', callback_data: 'draft:cancel' }]
    ]));
  }

  async #publish(chatId, userId, publishRequestId) {
    const session = this.draftStore.get(userId);
    if (!session || session.state !== BotState.WAITING_CONFIRMATION) {
      await this.telegram.sendMessage(chatId, 'Чернетка відсутня або вже оброблена.', mainKeyboard);
      return;
    }
    try {
      const result = await this.newsService.publish({
        ...session.draft,
        createdByTelegramId: userId,
        publishRequestId
      });
      this.draftStore.delete(userId);
      const active = await this.newsService.getPublished();
      const archivedLine = result.archived.length
        ? `\n\nАвтоматично перенесено в архів: ${result.archived.map((item) => item.title).join(', ')}.`
        : '';
      await this.telegram.sendMessage(chatId, `✅ Новину опубліковано.\n\nЗараз на сайті:\n${active.map((item, index) => `${index + 1}. ${item.title}`).join('\n')}${archivedLine}`, mainKeyboard);
    } catch (error) {
      this.logger.error('News publishing failed', error, { userId });
      await this.telegram.sendMessage(chatId, 'Публікація не завершена. Дані не підтверджені — спробуйте ще раз.');
    }
  }

  async #beginDraftEdit(chatId, userId, field) {
    const session = this.draftStore.get(userId);
    if (!session) return this.telegram.sendMessage(chatId, 'Чернетка відсутня.', mainKeyboard);
    if (field === 'media') {
      session.state = BotState.WAITING_EDIT_MEDIA;
      session.editScope = 'draft';
      this.draftStore.set(userId, session);
      await this.telegram.sendMessage(chatId, 'Надішліть нове фото або відео.');
      return;
    }
    session.state = BotState.WAITING_EDIT_VALUE;
    session.editScope = 'draft';
    session.editField = field;
    this.draftStore.set(userId, session);
    await this.telegram.sendMessage(chatId, `Надішліть нове значення (${field}).`);
  }

  async #saveEditValue(chatId, userId, session, text) {
    const field = session.editField;
    let value = sanitizeText(text);
    if (field === 'title' && (value.length < 3 || value.length > 120)) return this.telegram.sendMessage(chatId, 'Заголовок має містити від 3 до 120 символів.');
    if (field === 'description' && (value.length < 3 || value.length > 1500)) return this.telegram.sendMessage(chatId, 'Опис має містити від 3 до 1500 символів.');
    if (field === 'instagramUrl') {
      if (value === MENU.SKIP) value = '';
      const parsed = instagramUrlSchema.safeParse(value);
      if (!parsed.success) return this.telegram.sendMessage(chatId, 'Некоректне Instagram-посилання.');
      value = parsed.data;
    }

    if (session.editScope === 'draft') {
      session.draft[field] = value;
      session.state = BotState.WAITING_CONFIRMATION;
      delete session.editField;
      delete session.editScope;
      this.draftStore.set(userId, session);
      await this.#showPreview(chatId, session.draft);
      return;
    }

    await this.newsService.update(session.targetId, { [field]: value });
    this.draftStore.delete(userId);
    await this.telegram.sendMessage(chatId, '✅ Новину оновлено.', mainKeyboard);
  }

  async #showActive(chatId) {
    const active = await this.newsService.getActiveInternal();
    if (!active.length) return this.telegram.sendMessage(chatId, 'Активних новин немає.', mainKeyboard);
    await this.telegram.sendMessage(chatId, `Активні новини:\n${active.map((item, index) => `${index + 1}. ${item.title}`).join('\n')}`, inlineKeyboard(active.map((item, index) => [{ text: `${index + 1}. ${item.title.slice(0, 40)}`, callback_data: `news:${item.id}` }])));
  }

  async #showNews(chatId, id) {
    const record = await this.newsService.findById(id);
    if (!record || record.status !== 'published') return this.telegram.sendMessage(chatId, 'Активну новину не знайдено.');
    await this.telegram.sendMessage(chatId, summarize(record), inlineKeyboard([
      [{ text: '✏️ Змінити', callback_data: `edit:${id}` }, { text: '📁 Архівувати', callback_data: `archive:${id}` }],
      [{ text: '⬅️ Назад', callback_data: 'active:list' }]
    ]));
  }

  async #showEditMenu(chatId, id) {
    await this.telegram.sendMessage(chatId, 'Що змінити?', inlineKeyboard([
      [{ text: 'Заголовок', callback_data: `editfield:title:${id}` }, { text: 'Опис', callback_data: `editfield:description:${id}` }],
      [{ text: 'Instagram', callback_data: `editfield:instagramUrl:${id}` }, { text: 'Медіа', callback_data: `editfield:media:${id}` }],
      [{ text: '⬅️ Назад', callback_data: `news:${id}` }]
    ]));
  }

  async #beginPublishedEdit(chatId, userId, id, field) {
    const current = await this.newsService.findById(id);
    if (!current) return this.telegram.sendMessage(chatId, 'Новину не знайдено.');
    this.draftStore.set(userId, {
      state: field === 'media' ? BotState.WAITING_EDIT_MEDIA : BotState.WAITING_EDIT_VALUE,
      mode: 'edit',
      editScope: 'published',
      editField: field,
      targetId: id
    });
    await this.telegram.sendMessage(chatId, field === 'media' ? 'Надішліть нове фото або відео.' : `Надішліть нове значення (${field}).`);
  }

  async #archive(chatId, id) {
    const archived = await this.newsService.archive(id);
    await this.telegram.sendMessage(chatId, archived ? '✅ Новину перенесено в архів.' : 'Новину не знайдено.', mainKeyboard);
  }

  async #restore(chatId, id) {
    const restored = await this.newsService.restore(id);
    if (!restored) return this.telegram.sendMessage(chatId, 'Архівну новину не знайдено.');
    const archivedLine = restored.archived.length ? `\nВ архів переміщено: ${restored.archived.map((item) => item.title).join(', ')}.` : '';
    await this.telegram.sendMessage(chatId, `✅ Новину відновлено.${archivedLine}`, mainKeyboard);
  }

  async #showArchive(chatId, page) {
    const archive = await this.newsService.getArchive(page);
    if (!archive.items.length && page === 0) return this.telegram.sendMessage(chatId, 'Архів порожній.', mainKeyboard);
    const rows = archive.items.map((item) => [{ text: item.title.slice(0, 48), callback_data: `archived:${item.id}` }]);
    const navigation = [];
    if (archive.hasPrevious) navigation.push({ text: '⬅️', callback_data: `archivepage:${page - 1}` });
    if (archive.hasNext) navigation.push({ text: '➡️', callback_data: `archivepage:${page + 1}` });
    if (navigation.length) rows.push(navigation);
    await this.telegram.sendMessage(chatId, `Архів · сторінка ${page + 1}`, inlineKeyboard(rows));
  }

  async #showArchivedNews(chatId, id) {
    const record = await this.newsService.findById(id);
    if (!record || record.status !== 'archived') return this.telegram.sendMessage(chatId, 'Архівну новину не знайдено.');
    await this.telegram.sendMessage(chatId, summarize(record), inlineKeyboard([
      [{ text: '♻️ Відновити', callback_data: `restore:${id}` }],
      [{ text: '⬅️ До архіву', callback_data: 'archivepage:0' }]
    ]));
  }

  async #cancel(userId) {
    const session = this.draftStore.delete(userId);
    if (session?.mode === 'create' && session.draft?.cloudinaryPublicId) {
      await this.#removeQuietly(session.draft.cloudinaryPublicId, session.draft.mediaType);
    }
  }

  async #removeQuietly(publicId, mediaType) {
    try {
      await this.mediaService.remove(publicId, mediaType);
    } catch (error) {
      this.logger.warn('Cloudinary cleanup deferred', { publicId, error: error.message });
    }
  }

  async #safeAnswer(callbackId) {
    try { await this.telegram.answerCallbackQuery(callbackId); } catch (error) {
      this.logger.warn('Unable to answer Telegram callback', { error: error.message });
    }
  }
}
