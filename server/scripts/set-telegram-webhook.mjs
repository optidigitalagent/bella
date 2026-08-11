import { loadConfig } from '../src/config.mjs';
import { TelegramClient } from '../src/services/telegram.mjs';

const config = loadConfig();
if (!config.publicBaseUrl) throw new Error('PUBLIC_BASE_URL is required');
if (!config.telegram.botToken || !config.telegram.webhookSecret) throw new Error('Telegram token and webhook secret are required');

const telegram = new TelegramClient(config.telegram.botToken);
const webhookUrl = `${config.publicBaseUrl}/api/telegram/webhook`;
await telegram.setWebhook(webhookUrl, config.telegram.webhookSecret);
console.log(`Telegram webhook configured: ${webhookUrl}`);
