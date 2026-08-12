import { TelegramCms } from './bot/handlers.mjs';
import { LeadsService } from './services/leads-service.mjs';
import { TelegramClient } from './services/telegram.mjs';

export function createTelegramRuntime({
  config,
  repository,
  newsService,
  mediaService,
  draftStore,
  logger,
  TelegramClientClass = TelegramClient
}) {
  const cmsTelegram = new TelegramClientClass(config.telegram.cms.botToken);
  const leadsTelegram = new TelegramClientClass(config.telegram.leads.botToken);

  return {
    cmsTelegram,
    leadsTelegram,
    leadsService: new LeadsService({
      repository,
      telegram: leadsTelegram,
      adminIds: config.telegram.leads.adminIds
    }),
    telegramCms: new TelegramCms({
      telegram: cmsTelegram,
      newsService,
      mediaService,
      draftStore,
      adminIds: config.telegram.cms.adminIds,
      maxMediaBytes: config.cloudinary.maxMediaBytes,
      logger
    })
  };
}
