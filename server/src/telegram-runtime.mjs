import { TelegramCms } from './bot/handlers.mjs';
import { TelegramLeadsBot } from './bot/leads-handler.mjs';
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

  const leadsService = new LeadsService({
    repository,
    telegram: leadsTelegram,
    adminIds: config.telegram.leads.adminIds
  });

  return {
    cmsTelegram,
    leadsTelegram,
    leadsService,
    telegramLeadsBot: new TelegramLeadsBot({
      repository,
      telegram: leadsTelegram,
      adminIds: config.telegram.leads.adminIds,
      publicAccess: config.telegram.leads.publicAccess
    }),
    telegramCms: new TelegramCms({
      telegram: cmsTelegram,
      newsService,
      mediaService,
      draftStore,
      adminIds: config.telegram.cms.adminIds,
      publicAccess: config.telegram.cms.publicAccess,
      maxMediaBytes: config.cloudinary.maxMediaBytes,
      logger
    })
  };
}
