import { loadConfig } from '../src/config.mjs';
import { TelegramClient } from '../src/services/telegram.mjs';

const config = loadConfig();
if (!config.publicBaseUrl) throw new Error('PUBLIC_BASE_URL is required');
if (!config.telegram.cms.botToken || !config.telegram.cms.webhookSecret) throw new Error('CMS Telegram token and webhook secret are required');
if (!config.telegram.leads.botToken || !config.telegram.leads.webhookSecret) throw new Error('Leads Telegram token and webhook secret are required');

const cmsTelegram = new TelegramClient(config.telegram.cms.botToken);
const leadsTelegram = new TelegramClient(config.telegram.leads.botToken);
const cmsWebhookUrl = `${config.publicBaseUrl}/api/telegram/webhook`;
const leadsWebhookUrl = `${config.publicBaseUrl}/api/telegram/leads/webhook`;
await Promise.all([
  cmsTelegram.setWebhook(cmsWebhookUrl, config.telegram.cms.webhookSecret),
  leadsTelegram.setWebhook(leadsWebhookUrl, config.telegram.leads.webhookSecret)
]);
console.log(`CMS Telegram webhook configured: ${cmsWebhookUrl}`);
console.log(`Leads Telegram webhook configured: ${leadsWebhookUrl}`);
