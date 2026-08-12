import { createServer } from 'node:http';
import { loadConfig } from './config.mjs';
import { logger } from './lib/logger.mjs';
import { PostgresRepository } from './services/postgres.mjs';
import { CloudinaryMediaService } from './services/cloudinary.mjs';
import { NewsService } from './services/news-service.mjs';
import { DraftStore } from './bot/state.mjs';
import { createTelegramRuntime } from './telegram-runtime.mjs';
import { createApp } from './app.mjs';

const config = loadConfig();
const repository = PostgresRepository.fromConfig(config.database);
await repository.migrate();

const mediaService = new CloudinaryMediaService(config.cloudinary);
const newsService = new NewsService({ repository });
const draftStore = new DraftStore({
  ttlMs: config.draftTtlMs,
  onExpire: async (session) => {
    if (session?.mode === 'create' && session.draft?.cloudinaryPublicId) {
      try {
        await mediaService.remove(session.draft.cloudinaryPublicId, session.draft.mediaType);
      } catch (error) {
        logger.error('Expired draft media cleanup failed', error);
      }
    }
  }
});
const { leadsService, telegramCms } = createTelegramRuntime({
  config,
  repository,
  newsService,
  mediaService,
  draftStore,
  logger
});

const app = createApp({
  config,
  newsService,
  leadsService,
  telegramCms,
  healthCheck: () => repository.ping(),
  logger
});
const server = createServer(app);

server.listen(config.port, '0.0.0.0', () => {
  logger.info('Bella Dent backend listening', { port: config.port, environment: config.nodeEnv });
});

function shutdown(signal) {
  logger.info('Graceful shutdown requested', { signal });
  draftStore.close();
  server.close(async (error) => {
    if (error) {
      logger.error('Server shutdown failed', error);
      process.exitCode = 1;
    }
    await repository.close();
    process.exit();
  });
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
