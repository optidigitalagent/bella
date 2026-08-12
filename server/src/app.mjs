import { timingSafeEqual } from 'node:crypto';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { rateLimit } from 'express-rate-limit';
import { ZodError } from 'zod';
import { leadSchema } from './validation.mjs';
import { ExternalServiceError, HttpError } from './lib/errors.mjs';
import { logger as defaultLogger } from './lib/logger.mjs';

function secureEqual(actual, expected) {
  const actualBuffer = Buffer.from(String(actual || ''));
  const expectedBuffer = Buffer.from(String(expected || ''));
  return actualBuffer.length === expectedBuffer.length && timingSafeEqual(actualBuffer, expectedBuffer);
}

export function createApp({ config, newsService, leadsService, telegramCms, healthCheck = async () => true, logger = defaultLogger }) {
  const app = express();
  app.disable('x-powered-by');
  app.set('trust proxy', 1);
  app.use(helmet());
  app.use(express.json({ limit: '64kb', strict: true }));
  app.use(cors({
    origin(origin, callback) {
      if (!origin || config.allowedOrigins.has(origin.replace(/\/$/, ''))) return callback(null, true);
      return callback(new HttpError(403, 'ORIGIN_NOT_ALLOWED', 'Origin is not allowed'));
    },
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type'],
    maxAge: 600
  }));

  app.get('/health', async (_request, response, next) => {
    try {
      const databaseHealthy = await healthCheck();
      if (!databaseHealthy) throw new Error('Database health check failed');
      response.set('Cache-Control', 'no-store').json({ status: 'ok', database: 'ok' });
    } catch (error) {
      next(error);
    }
  });

  app.get('/api/news', async (_request, response, next) => {
    try {
      const news = await newsService.getPublished();
      response.set('Cache-Control', 'no-store').json(news);
    } catch (error) {
      next(error);
    }
  });

  const leadLimiter = rateLimit({
    windowMs: config.rateLimits.leadWindowMs,
    limit: config.rateLimits.leadMax,
    standardHeaders: 'draft-8',
    legacyHeaders: false,
    message: { error: 'RATE_LIMITED', message: 'Too many requests' }
  });

  app.post('/api/leads', leadLimiter, async (request, response, next) => {
    try {
      const parsed = leadSchema.parse(request.body);
      if (parsed.website) {
        response.status(204).end();
        return;
      }
      const result = await leadsService.submit(parsed);
      response.status(201).json({ ok: true, id: result.id });
    } catch (error) {
      next(error);
    }
  });

  const webhookLimiter = rateLimit({
    windowMs: config.rateLimits.webhookWindowMs,
    limit: config.rateLimits.webhookMax,
    standardHeaders: false,
    legacyHeaders: false,
    message: { error: 'RATE_LIMITED' }
  });

  app.post('/api/telegram/webhook', (request, response, next) => {
    const supplied = request.get('X-Telegram-Bot-Api-Secret-Token');
    if (!secureEqual(supplied, config.telegram.cms.webhookSecret)) {
      next(new HttpError(401, 'UNAUTHORIZED', 'Unauthorized'));
      return;
    }
    next();
  }, webhookLimiter, async (request, response, next) => {
    try {
      await telegramCms.handleUpdate(request.body);
      response.status(200).json({ ok: true });
    } catch (error) {
      next(error);
    }
  });

  app.use((_request, response) => {
    response.status(404).json({ error: 'NOT_FOUND', message: 'Endpoint not found' });
  });

  app.use((error, request, response, _next) => {
    if (error instanceof ZodError) {
      response.status(400).json({
        error: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        fields: error.issues.map((issue) => ({ path: issue.path.join('.'), message: issue.message }))
      });
      return;
    }
    if (error instanceof HttpError) {
      response.status(error.status).json({ error: error.code, message: error.message });
      return;
    }
    const external = error instanceof ExternalServiceError;
    logger.error('Request failed', error, { method: request.method, path: request.path });
    response.status(external ? 502 : 500).json({
      error: external ? 'UPSTREAM_ERROR' : 'INTERNAL_ERROR',
      message: external ? 'A required service did not confirm the operation' : 'Unexpected server error'
    });
  });

  return app;
}
