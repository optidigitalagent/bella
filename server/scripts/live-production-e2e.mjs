import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';

if (process.env.ALLOW_PRODUCTION_MUTATION !== '1') {
  throw new Error('Set ALLOW_PRODUCTION_MUTATION=1 to acknowledge that this script writes production QA records');
}

const required = ['PUBLIC_BASE_URL', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_ADMIN_IDS', 'TELEGRAM_WEBHOOK_SECRET'];
for (const name of required) {
  if (!process.env[name]) throw new Error(`Missing ${name}`);
}

const baseUrl = process.env.PUBLIC_BASE_URL.replace(/\/$/, '');
const botToken = process.env.TELEGRAM_BOT_TOKEN;
const adminId = String(process.env.TELEGRAM_ADMIN_IDS).split(',')[0].trim();
const webhookSecret = process.env.TELEGRAM_WEBHOOK_SECRET;
const telegramBase = `https://api.telegram.org/bot${botToken}`;
const runId = `qa-${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}-${randomUUID().slice(0, 8)}`;
let updateId = Math.floor(Date.now() / 1000);
let messageId = 1000;

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function telegram(method, body) {
  const response = await fetch(`${telegramBase}/${method}`, {
    method: 'POST',
    body: body instanceof FormData ? body : JSON.stringify(body),
    headers: body instanceof FormData ? undefined : { 'content-type': 'application/json' }
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(`Telegram ${method} failed: ${data.description || response.status}`);
  return data.result;
}

async function webhook(payload) {
  const response = await fetch(`${baseUrl}/api/telegram/webhook`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-telegram-bot-api-secret-token': webhookSecret
    },
    body: JSON.stringify({ update_id: updateId++, ...payload })
  });
  if (!response.ok) throw new Error(`Webhook failed (${response.status}): ${await response.text()}`);
}

function user() {
  return { id: Number(adminId), is_bot: false, first_name: 'Production QA' };
}

function chat() {
  return { id: Number(adminId), type: 'private' };
}

async function sendText(text) {
  await webhook({
    message: {
      message_id: messageId++,
      date: Math.floor(Date.now() / 1000),
      from: user(),
      chat: chat(),
      text
    }
  });
}

async function sendPhoto(file) {
  await webhook({
    message: {
      message_id: messageId++,
      date: Math.floor(Date.now() / 1000),
      from: user(),
      chat: chat(),
      photo: [{
        file_id: file.file_id,
        file_unique_id: file.file_unique_id,
        width: file.width,
        height: file.height,
        file_size: file.file_size
      }]
    }
  });
}

async function callback(data) {
  await webhook({
    callback_query: {
      id: `${runId}-${messageId++}`,
      from: user(),
      message: {
        message_id: messageId++,
        date: Math.floor(Date.now() / 1000),
        chat: chat()
      },
      chat_instance: runId,
      data
    }
  });
}

async function active() {
  const response = await fetch(`${baseUrl}/api/news`, { headers: { accept: 'application/json' } });
  assert(response.ok, `GET /api/news failed: ${response.status}`);
  const data = await response.json();
  assert(Array.isArray(data), 'GET /api/news did not return an array');
  return data;
}

function assertTitles(actual, expected, stage) {
  const titles = actual.map((item) => item.title);
  assert(JSON.stringify(titles) === JSON.stringify(expected), `${stage}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(titles)}`);
  console.log(`${stage}: ${titles.join(' > ') || '(empty)'}`);
}

const initialActive = await active();
assert(initialActive.length === 0, 'Production QA requires an empty active-news window to avoid archiving real content');

const imageBytes = await readFile(new URL('../../bella-dent-logo.png.png', import.meta.url));
const form = new FormData();
form.set('chat_id', adminId);
form.set('caption', `Bella Dent production image test ${runId}`);
form.set('photo', new Blob([imageBytes], { type: 'image/png' }), `${runId}.png`);
const sentPhoto = await telegram('sendPhoto', form);
const photo = sentPhoto.photo.at(-1);
assert(photo?.file_id, 'Telegram did not return a photo file_id');
console.log(`REAL_IMAGE: Telegram accepted ${photo.file_size || imageBytes.length} bytes`);

const webhookInfo = await telegram('getWebhookInfo', {});
assert(webhookInfo.url === `${baseUrl}/api/telegram/webhook`, `Unexpected webhook URL: ${webhookInfo.url}`);
assert(Number(webhookInfo.pending_update_count || 0) === 0, `Webhook has ${webhookInfo.pending_update_count} pending updates`);
console.log('WEBHOOK: configured, reachable, zero pending updates');

async function runCmsAcceptance() {
  await sendText('/start');

  const created = new Map();
  const expected = [];
  let cloudinaryVerified = false;
  for (const letter of ['A', 'B', 'C', 'D', 'E']) {
    const title = `LIVE QA ${letter} ${runId}`;
    await sendText('➕ Додати новину');
    await sendText(title);
    await sendText(`Production end-to-end verification record ${letter} for ${runId}.`);
    await sendPhoto(photo);
    await sendText('Пропустити');
    await callback('publish');
    expected.unshift(title);
    if (expected.length > 3) expected.length = 3;
    const records = await active();
    assertTitles(records, expected, `ROLLING_${letter}`);
    const published = records.find((record) => record.title === title);
    assert(published?.mediaType === 'image', `${letter}: published record media type is not image`);
    assert(published?.mediaUrl, `${letter}: published record has no media URL`);
    const mediaHost = new URL(published.mediaUrl).hostname;
    assert(mediaHost === 'res.cloudinary.com', `${letter}: unexpected media host ${mediaHost}`);
    if (!cloudinaryVerified) {
      const mediaResponse = await fetch(published.mediaUrl);
      assert(mediaResponse.ok, `Cloudinary delivery failed: ${mediaResponse.status}`);
      cloudinaryVerified = true;
      console.log('CLOUDINARY: uploaded media is publicly deliverable');
    }
    for (const record of records) created.set(record.title, record);
  }

  await sendText('📰 Активні новини');

  const dTitle = `LIVE QA D ${runId}`;
  const d = created.get(dTitle);
  assert(d?.id, 'Unable to identify D record');
  await callback(`archive:${d.id}`);
  assertTitles(await active(), [`LIVE QA E ${runId}`, `LIVE QA C ${runId}`], 'ARCHIVE_D');
  await sendText('📁 Архів');
  await callback(`archived:${d.id}`);
  await callback(`restore:${d.id}`);
  assertTitles(await active(), [dTitle, `LIVE QA E ${runId}`, `LIVE QA C ${runId}`], 'RESTORE_D');

  await callback(`edit:${d.id}`);
  await callback(`editfield:title:${d.id}`);
  const editedDTitle = `LIVE QA D EDITED ${runId}`;
  await sendText(editedDTitle);
  assertTitles(await active(), [editedDTitle, `LIVE QA E ${runId}`, `LIVE QA C ${runId}`], 'EDIT_D');

  return { created, editedId: d.id };
}

let result;
try {
  result = await runCmsAcceptance();
} finally {
  const qaRecords = (await active()).filter((record) => record.title.includes(runId));
  for (const record of qaRecords) await callback(`archive:${record.id}`);
  const remainingQaRecords = (await active()).filter((record) => record.title.includes(runId));
  assertTitles(remainingQaRecords, [], 'CLEAN_ACTIVE_WINDOW');
  await sendText('📁 Архів');
}

console.log(JSON.stringify({
  runId,
  createdIds: [...result.created.values()].map((record) => record.id),
  editedId: result.editedId,
  finalActiveCount: 0
}));
