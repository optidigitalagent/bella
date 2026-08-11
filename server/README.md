# Bella Dent Clinic Life backend

One Node.js 20+ Railway service provides:

- `GET /health`
- `GET /api/news`
- `POST /api/leads`
- `POST /api/telegram/webhook`
- Telegram CMS for create, active list, edit, archive, archive paging, and restore
- Telegram media download and Cloudinary upload
- Google Sheets persistence and the rolling window of three published news

The service is deterministic and does not use OpenAI or another LLM.

## Local commands

```powershell
cd server
npm install
Copy-Item .env.example .env
# Populate the variables in your local environment or load them with your preferred env manager.
npm run sheets:init
npm start
```

This project intentionally does not auto-load `.env`; Railway injects Variables directly. For local PowerShell, set variables in the current process before starting, for example `$env:PORT='3000'`. Never commit the populated values.

Tests do not call Telegram, Cloudinary, or Google:

```powershell
cd server
npm test
npm run test:coverage
```

## Railway service

1. Create one Railway service from this GitHub repository.
2. Set the service root directory to `/server`.
3. In service settings, set the config file path explicitly to `/server/railway.json`. Railway's config-file lookup does not follow the service Root Directory automatically.
4. Keep exactly one replica/process for the MVP. The publish mutex is process-local because Google Sheets does not provide transactions.
5. Generate a public Railway domain and set its HTTPS origin as `PUBLIC_BASE_URL` (no trailing slash). You may derive it from Railway's `RAILWAY_PUBLIC_DOMAIN` reference variable.
6. Add all Variables listed below.
7. The service starts with `npm start`, binds to Railway's `PORT`, and exposes `/health` for health checks.
8. After a successful health check, run `npm run sheets:init` once from the Railway shell or locally with the production Variables.
9. Run `npm run telegram:set-webhook` once. It registers `${PUBLIC_BASE_URL}/api/telegram/webhook` with Telegram and supplies `TELEGRAM_WEBHOOK_SECRET` as Telegram's secret token.
10. Configure the same public origin once in root [`site-config.js`](../site-config.js), then publish the static frontend. New news after that require no Git commit or frontend redeploy.

Do not scale beyond one replica until the in-process mutex is replaced by a distributed lock or a transactional datastore.

## Railway Variables

| Variable | Required | Meaning |
| --- | --- | --- |
| `NODE_ENV=production` | yes | Enables strict production credential checks. |
| `PORT` | Railway | Supplied by Railway. |
| `PUBLIC_BASE_URL` | yes | Public Railway origin, e.g. `https://service.up.railway.app`. |
| `SITE_ORIGIN` | yes | `https://belladentclinik.kr.ua`. |
| `ALLOWED_ORIGINS` | yes | Comma-separated exact origins: `https://belladentclinik.kr.ua,https://optidigitalagent.github.io`. |
| `TELEGRAM_BOT_TOKEN` | yes | BotFather token. |
| `TELEGRAM_ADMIN_IDS` | yes | Comma-separated numeric user IDs allowed to use the CMS and receive leads. |
| `TELEGRAM_WEBHOOK_SECRET` | yes | Random secret sent/verified through `X-Telegram-Bot-Api-Secret-Token`. Use only URL-safe characters. |
| `CLOUDINARY_CLOUD_NAME` | yes | Cloudinary cloud name. |
| `CLOUDINARY_API_KEY` | yes | Cloudinary server-side API key. |
| `CLOUDINARY_API_SECRET` | yes | Cloudinary server-side API secret. |
| `CLOUDINARY_FOLDER` | yes | Recommended: `bella-dent/news`. |
| `MAX_MEDIA_BYTES` | yes | Default `20000000` (20 MB). Telegram metadata and downloaded bytes are both checked. |
| `GOOGLE_SHEET_ID` | yes | Spreadsheet ID between `/d/` and `/edit`. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | one of two | Raw service-account JSON. Newlines in `private_key` may be escaped as `\n`. |
| `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` | one of two | Base64 of the complete JSON; recommended if raw multiline JSON is inconvenient. |
| `NEWS_SHEET_NAME` | yes | Default `News`. |
| `LEADS_SHEET_NAME` | yes | Default `Leads`. |
| `LEAD_RATE_LIMIT_WINDOW_MS` | yes | Default `900000`. |
| `LEAD_RATE_LIMIT_MAX` | yes | Default `5` per IP/window. |
| `WEBHOOK_RATE_LIMIT_WINDOW_MS` | yes | Default `60000`. |
| `WEBHOOK_RATE_LIMIT_MAX` | yes | Default `120` per IP/window after secret validation. |
| `DRAFT_TTL_MS` | yes | Default `3600000` (one hour). |

Generate a webhook secret locally without printing other credentials:

```powershell
node -e "console.log(require('node:crypto').randomBytes(32).toString('base64url'))"
```

## Google Sheets setup

1. Create one spreadsheet owned by the clinic.
2. In Google Cloud, create or select a project, enable Google Sheets API, create a service account, and create its JSON key.
3. Share the spreadsheet with the service account's `client_email` as Editor. The spreadsheet does not need to be public.
4. Set `GOOGLE_SHEET_ID` and one service-account JSON Variable.
5. Run `npm run sheets:init`.

The initializer is non-destructive. It creates missing `News` and `Leads` tabs and writes headers only when row 1 is empty. If an existing header row differs, it stops instead of overwriting data.

`News` headers:

```text
id,status,published_at,updated_at,archived_at,title,description,media_type,media_url,cloudinary_public_id,instagram_url,created_by_telegram_id,publish_request_id
```

`Leads` headers:

```text
id,created_at,name,phone,comment,source,status,request_id
```

`request_id` makes a successful browser submission idempotent when the same request is retried.

## Telegram Bot setup

1. Open `@BotFather`, run `/newbot`, and store the token only in `TELEGRAM_BOT_TOKEN`.
2. Obtain each administrator's numeric Telegram user ID (for example through a trusted ID bot or a temporary `getUpdates` check before enabling the webhook).
3. Put only those numeric IDs in `TELEGRAM_ADMIN_IDS`.
4. Set a random `TELEGRAM_WEBHOOK_SECRET`.
5. Deploy and verify `GET ${PUBLIC_BASE_URL}/health`.
6. Run `npm run telegram:set-webhook`.
7. In the bot, `/start` shows:

```text
Bella Dent — управління сайтом
➕ Додати новину
📰 Активні новини
📁 Архів
```

Non-whitelisted IDs receive a neutral refusal. Production does not use long polling, so there is no webhook/polling conflict.

## Cloudinary setup

1. Create or select the clinic's Cloudinary product environment.
2. Copy cloud name, API key, and API secret to Railway Variables.
3. Keep `CLOUDINARY_FOLDER=bella-dent/news`.
4. No unsigned upload preset is required; all uploads are signed server-side.
5. Staff send normal Telegram photos/videos. The backend downloads, size/type checks, uploads, and stores only `secure_url` plus `public_id` in Sheets.

Canceled/expired draft assets are deleted where possible. During media replacement, the old asset is deleted only after the new Sheet value is saved. Published assets are retained when a news item is archived.

## Frontend API setting

Edit one line only after Railway has a domain:

```js
window.BELLA_API_BASE = 'https://YOUR-SERVICE.up.railway.app';
```

Until this value exists, the Clinic Life section stays hidden and the lead form reports that online submission is unavailable. It never shows a fake success.

## Production verification

Run a real credential-backed check in this order:

1. `/health` returns `{"status":"ok"}`.
2. `/api/news` returns an array and `Cache-Control: no-store`.
3. Telegram admin `/start` works; a non-admin is denied.
4. Publish A, B, C, D, E with real media and verify Cloudinary assets plus Sheet rows.
5. Confirm the active sequence is `A`; `B,A`; `C,B,A`; `D,C,B` with A archived; `E,D,C` with B archived.
6. Confirm the deployed website changes from A through E without a frontend commit or redeploy.
7. Test Active News, Edit (including media replacement), Archive, and Restore.
8. Submit one real website lead and confirm both the Telegram delivery and the `Leads` row with status `delivered`.

Without real Telegram, Cloudinary, Google, Railway, and deployed frontend configuration, these steps remain blocked and must not be reported as passed.
