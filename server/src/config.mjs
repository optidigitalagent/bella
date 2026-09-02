import { z } from 'zod';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().positive().max(65535).default(3000),
  PUBLIC_BASE_URL: z.string().trim().default(''),
  SITE_ORIGIN: z.string().url().default('https://belladentclinik.kr.ua'),
  ALLOWED_ORIGINS: z.string().default('https://belladentclinik.kr.ua,https://optidigitalagent.github.io'),
  TELEGRAM_BOT_TOKEN: z.string().trim().default(''),
  TELEGRAM_ADMIN_IDS: z.string().trim().default(''),
  TELEGRAM_CMS_PUBLIC_ACCESS: z.enum(['true', 'false']).default('true'),
  TELEGRAM_WEBHOOK_SECRET: z.string().trim().default(''),
  TELEGRAM_LEADS_BOT_TOKEN: z.string().trim().default(''),
  TELEGRAM_LEADS_ADMIN_IDS: z.string().trim().default(''),
  TELEGRAM_LEADS_PUBLIC_ACCESS: z.enum(['true', 'false']).default('true'),
  TELEGRAM_LEADS_WEBHOOK_SECRET: z.string().trim().default(''),
  CLOUDINARY_CLOUD_NAME: z.string().trim().default(''),
  CLOUDINARY_API_KEY: z.string().trim().default(''),
  CLOUDINARY_API_SECRET: z.string().trim().default(''),
  CLOUDINARY_FOLDER: z.string().trim().default('bella-dent/news'),
  MAX_MEDIA_BYTES: z.coerce.number().int().positive().default(20_000_000),
  DATABASE_URL: z.string().trim().default(''),
  DATABASE_POOL_MAX: z.coerce.number().int().positive().max(50).default(10),
  DATABASE_CONNECTION_TIMEOUT_MS: z.coerce.number().int().positive().default(10_000),
  DATABASE_IDLE_TIMEOUT_MS: z.coerce.number().int().positive().default(30_000),
  LEAD_RATE_LIMIT_WINDOW_MS: z.coerce.number().int().positive().default(900_000),
  LEAD_RATE_LIMIT_MAX: z.coerce.number().int().positive().default(5),
  WEBHOOK_RATE_LIMIT_WINDOW_MS: z.coerce.number().int().positive().default(60_000),
  WEBHOOK_RATE_LIMIT_MAX: z.coerce.number().int().positive().default(120),
  DRAFT_TTL_MS: z.coerce.number().int().positive().default(3_600_000)
});

function parseAdminIds(value, variableName) {
  if (!value) return [];
  const parsed = value.split(',').map((item) => item.trim());
  if (parsed.some((id) => !/^\d+$/.test(id))) {
    throw new Error(`${variableName} must contain only comma-separated numeric IDs`);
  }
  return [...new Set(parsed)];
}

export function loadConfig(source = process.env) {
  const env = envSchema.parse(source);
  const cmsAdminIds = parseAdminIds(env.TELEGRAM_ADMIN_IDS, 'TELEGRAM_ADMIN_IDS');
  const leadsAdminIds = parseAdminIds(env.TELEGRAM_LEADS_ADMIN_IDS, 'TELEGRAM_LEADS_ADMIN_IDS');
  for (const [name, value] of [
    ['TELEGRAM_WEBHOOK_SECRET', env.TELEGRAM_WEBHOOK_SECRET],
    ['TELEGRAM_LEADS_WEBHOOK_SECRET', env.TELEGRAM_LEADS_WEBHOOK_SECRET]
  ]) {
    if (value && !/^[A-Za-z0-9_-]{1,256}$/.test(value)) {
      throw new Error(`${name} must contain 1-256 URL-safe characters`);
    }
  }
  if (env.NODE_ENV === 'production') {
    const required = [
      'PUBLIC_BASE_URL', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_WEBHOOK_SECRET',
      'TELEGRAM_LEADS_BOT_TOKEN',
      'CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET', 'DATABASE_URL'
    ];
    const missing = required.filter((name) => !env[name]);
    if (missing.length) throw new Error(`Missing required production variables: ${missing.join(', ')}`);
    const publicUrl = new URL(env.PUBLIC_BASE_URL);
    if (publicUrl.protocol !== 'https:') throw new Error('PUBLIC_BASE_URL must use HTTPS in production');
  }
  return {
    nodeEnv: env.NODE_ENV,
    port: env.PORT,
    publicBaseUrl: env.PUBLIC_BASE_URL.replace(/\/$/, ''),
    siteOrigin: env.SITE_ORIGIN.replace(/\/$/, ''),
    allowedOrigins: new Set(env.ALLOWED_ORIGINS.split(',').map((item) => item.trim().replace(/\/$/, '')).filter(Boolean)),
    telegram: {
      cms: {
        botToken: env.TELEGRAM_BOT_TOKEN,
        adminIds: cmsAdminIds,
        publicAccess: env.TELEGRAM_CMS_PUBLIC_ACCESS === 'true',
        webhookSecret: env.TELEGRAM_WEBHOOK_SECRET
      },
      leads: {
        botToken: env.TELEGRAM_LEADS_BOT_TOKEN,
        adminIds: leadsAdminIds,
        publicAccess: env.TELEGRAM_LEADS_PUBLIC_ACCESS === 'true',
        webhookSecret: env.TELEGRAM_LEADS_WEBHOOK_SECRET || env.TELEGRAM_WEBHOOK_SECRET
      }
    },
    cloudinary: {
      cloudName: env.CLOUDINARY_CLOUD_NAME,
      apiKey: env.CLOUDINARY_API_KEY,
      apiSecret: env.CLOUDINARY_API_SECRET,
      folder: env.CLOUDINARY_FOLDER,
      maxMediaBytes: env.MAX_MEDIA_BYTES
    },
    database: {
      databaseUrl: env.DATABASE_URL,
      poolMax: env.DATABASE_POOL_MAX,
      connectionTimeoutMs: env.DATABASE_CONNECTION_TIMEOUT_MS,
      idleTimeoutMs: env.DATABASE_IDLE_TIMEOUT_MS
    },
    rateLimits: {
      leadWindowMs: env.LEAD_RATE_LIMIT_WINDOW_MS,
      leadMax: env.LEAD_RATE_LIMIT_MAX,
      webhookWindowMs: env.WEBHOOK_RATE_LIMIT_WINDOW_MS,
      webhookMax: env.WEBHOOK_RATE_LIMIT_MAX
    },
    draftTtlMs: env.DRAFT_TTL_MS
  };
}
