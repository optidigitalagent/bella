import { loadConfig } from '../src/config.mjs';
import { TelegramClient } from '../src/services/telegram.mjs';

const config = loadConfig();
if (!config.publicBaseUrl) throw new Error('PUBLIC_BASE_URL is required');
if (!config.telegram.cms.botToken || !config.telegram.cms.webhookSecret) throw new Error('CMS Telegram token and webhook secret are required');

const telegram = new TelegramClient(config.telegram.cms.botToken);
const webhookUrl = `${config.publicBaseUrl}/api/telegram/webhook`;
await telegram.setWebhook(webhookUrl, config.telegram.cms.webhookSecret);
console.log(`Telegram webhook configured: ${webhookUrl}`);
