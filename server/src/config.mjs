import { z } from 'zod';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().positive().max(65535).default(3000),
  PUBLIC_BASE_URL: z.string().trim().default(''),
  SITE_ORIGIN: z.string().url().default('https://belladentclinik.kr.ua'),
  ALLOWED_ORIGINS: z.string().default('https://belladentclinik.kr.ua,https://optidigitalagent.github.io'),
  TELEGRAM_BOT_TOKEN: z.string().trim().default(''),
  TELEGRAM_ADMIN_IDS: z.string().trim().default(''),
  TELEGRAM_WEBHOOK_SECRET: z.string().trim().default(''),
  CLOUDINARY_CLOUD_NAME: z.string().trim().default(''),
  CLOUDINARY_API_KEY: z.string().trim().default(''),
  CLOUDINARY_API_SECRET: z.string().trim().default(''),
  CLOUDINARY_FOLDER: z.string().trim().default('bella-dent/news'),
  MAX_MEDIA_BYTES: z.coerce.number().int().positive().default(20_000_000),
  GOOGLE_SHEET_ID: z.string().trim().default(''),
  GOOGLE_SERVICE_ACCOUNT_JSON: z.string().default(''),
  GOOGLE_SERVICE_ACCOUNT_JSON_BASE64: z.string().default(''),
  NEWS_SHEET_NAME: z.string().trim().default('News'),
  LEADS_SHEET_NAME: z.string().trim().default('Leads'),
  LEAD_RATE_LIMIT_WINDOW_MS: z.coerce.number().int().positive().default(900_000),
  LEAD_RATE_LIMIT_MAX: z.coerce.number().int().positive().default(5),
  WEBHOOK_RATE_LIMIT_WINDOW_MS: z.coerce.number().int().positive().default(60_000),
  WEBHOOK_RATE_LIMIT_MAX: z.coerce.number().int().positive().default(120),
  DRAFT_TTL_MS: z.coerce.number().int().positive().default(3_600_000)
});

function parseAdminIds(value) {
  return [...new Set(value.split(',').map((item) => item.trim()).filter(Boolean))];
}

export function loadConfig(source = process.env) {
  const env = envSchema.parse(source);
  const adminIds = parseAdminIds(env.TELEGRAM_ADMIN_IDS);
  if (adminIds.some((id) => !/^\d+$/.test(id))) throw new Error('TELEGRAM_ADMIN_IDS must contain only comma-separated numeric IDs');
  if (env.TELEGRAM_WEBHOOK_SECRET && !/^[A-Za-z0-9_-]{1,256}$/.test(env.TELEGRAM_WEBHOOK_SECRET)) {
    throw new Error('TELEGRAM_WEBHOOK_SECRET must contain 1-256 URL-safe characters');
  }
  if (env.NODE_ENV === 'production') {
    const required = [
      'PUBLIC_BASE_URL', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_ADMIN_IDS', 'TELEGRAM_WEBHOOK_SECRET',
      'CLOUDINARY_CLOUD_NAME', 'CLOUDINARY_API_KEY', 'CLOUDINARY_API_SECRET', 'GOOGLE_SHEET_ID'
    ];
    const missing = required.filter((name) => !env[name]);
    if (!env.GOOGLE_SERVICE_ACCOUNT_JSON && !env.GOOGLE_SERVICE_ACCOUNT_JSON_BASE64) {
      missing.push('GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_JSON_BASE64');
    }
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
      botToken: env.TELEGRAM_BOT_TOKEN,
      adminIds,
      webhookSecret: env.TELEGRAM_WEBHOOK_SECRET
    },
    cloudinary: {
      cloudName: env.CLOUDINARY_CLOUD_NAME,
      apiKey: env.CLOUDINARY_API_KEY,
      apiSecret: env.CLOUDINARY_API_SECRET,
      folder: env.CLOUDINARY_FOLDER,
      maxMediaBytes: env.MAX_MEDIA_BYTES
    },
    google: {
      sheetId: env.GOOGLE_SHEET_ID,
      serviceAccountJson: env.GOOGLE_SERVICE_ACCOUNT_JSON,
      serviceAccountJsonBase64: env.GOOGLE_SERVICE_ACCOUNT_JSON_BASE64,
      newsSheetName: env.NEWS_SHEET_NAME,
      leadsSheetName: env.LEADS_SHEET_NAME
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
