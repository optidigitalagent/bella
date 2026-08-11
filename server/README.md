# Bella Dent Clinic Life backend

One Node.js 20+ Railway service provides:

- `GET /health` with a live PostgreSQL connectivity check
- `GET /api/news`
- `POST /api/leads`
- `POST /api/telegram/webhook`
- Telegram CMS create, edit, archive, paginated archive, and restore flows
- Telegram media download and Cloudinary upload
- PostgreSQL persistence with transactional rolling publication and request idempotency

The backend has no Google Sheets runtime dependency. News and leads are stored in PostgreSQL; media binaries remain in Cloudinary and only their `secure_url`, public ID, and media type are stored in the database.

## Local commands

```powershell
cd server
npm install
Copy-Item .env.example .env
# Load the variables with your preferred environment manager.
npm run db:migrate
npm start
```

This project intentionally does not auto-load `.env`; Railway injects Variables directly. For local PowerShell, set variables in the current process before starting. Never commit populated values.

```powershell
npm test
npm run test:coverage
npm run test:browser
```

Database integration tests use `TEST_DATABASE_URL`. They create and remove a uniquely named test schema and never truncate production tables.

## Railway architecture

```text
Telegram -> bella-dent-api -> PostgreSQL -> website API
                       |----> Cloudinary

Website lead -> bella-dent-api -> PostgreSQL -> Telegram admins
```

1. Keep the API service root directory at `/server` and config path at `/server/railway.json`.
2. Add a PostgreSQL service to the same Railway project.
3. On `bella-dent-api`, set `DATABASE_URL=${{Postgres.DATABASE_URL}}`. This uses Railway private networking; do not copy database credentials into client code or the static site.
4. Deploy normally. Startup runs versioned, idempotent migrations before binding the HTTP port.
5. Generate a public API domain and set it as `PUBLIC_BASE_URL` without a trailing slash.
6. Verify `/health` returns `{"status":"ok","database":"ok"}`.
7. Run `npm run telegram:set-webhook` after deployment.

The rolling maximum-three rule uses a PostgreSQL transaction and transaction-scoped advisory lock. Multiple API replicas are safe for publish/restore and duplicate request handling.

## Railway variables

| Variable | Required | Meaning |
| --- | --- | --- |
| `NODE_ENV=production` | yes | Enables strict production validation. |
| `PORT` | Railway | Supplied by Railway. |
| `PUBLIC_BASE_URL` | yes | Public Railway API origin. |
| `SITE_ORIGIN` | yes | Canonical clinic website origin. |
| `ALLOWED_ORIGINS` | yes | Comma-separated exact browser origins. |
| `DATABASE_URL` | yes | Use `${{Postgres.DATABASE_URL}}`; server-side only. |
| `DATABASE_POOL_MAX` | no | Pool size; default `10`. |
| `DATABASE_CONNECTION_TIMEOUT_MS` | no | Default `10000`. |
| `DATABASE_IDLE_TIMEOUT_MS` | no | Default `30000`. |
| `TELEGRAM_BOT_TOKEN` | yes | BotFather token. |
| `TELEGRAM_ADMIN_IDS` | yes | Comma-separated numeric CMS/admin IDs. |
| `TELEGRAM_WEBHOOK_SECRET` | yes | URL-safe Telegram webhook secret. |
| `CLOUDINARY_CLOUD_NAME` | yes | Cloudinary cloud name. |
| `CLOUDINARY_API_KEY` | yes | Server-side API key. |
| `CLOUDINARY_API_SECRET` | yes | Server-side API secret. |
| `CLOUDINARY_FOLDER` | no | Default `bella-dent/news`. |
| `MAX_MEDIA_BYTES` | no | Default `20000000`. |
| `LEAD_RATE_LIMIT_WINDOW_MS` | no | Default `900000`. |
| `LEAD_RATE_LIMIT_MAX` | no | Default `5`. |
| `WEBHOOK_RATE_LIMIT_WINDOW_MS` | no | Default `60000`. |
| `WEBHOOK_RATE_LIMIT_MAX` | no | Default `120`. |
| `DRAFT_TTL_MS` | no | Default one hour. |

## Database and migrations

`src/db/migrations.mjs` contains ordered migrations. `schema_migrations` records each applied version. Both automatic startup and `npm run db:migrate` acquire a database advisory lock, so concurrent deployments cannot apply the same migration twice.

`news.publish_request_id` and `leads.request_id` are unique. News statuses are `draft`, `published`, and `archived`. Lead delivery statuses are `received`, `notification_failed`, and `delivered`.

Publishing and restoring serialize in PostgreSQL, make the selected item newest, and archive everything outside the newest three in the same transaction. Duplicate publish IDs return the original item. Duplicate delivered lead IDs do not send Telegram twice. A Telegram delivery failure is committed as `notification_failed`, and the API returns an upstream error rather than fake success.

## Cloudinary and Telegram

Cloudinary uploads are signed server-side. PostgreSQL stores no binary media. Canceled/expired draft assets are removed where possible; replacement deletes the prior asset only after the new database value is committed.

The Telegram webhook is `${PUBLIC_BASE_URL}/api/telegram/webhook` and is protected by `X-Telegram-Bot-Api-Secret-Token`. Only IDs in `TELEGRAM_ADMIN_IDS` can use the CMS or receive leads.

Generate a webhook secret without printing other credentials:

```powershell
node -e "console.log(require('node:crypto').randomBytes(32).toString('base64url'))"
```

## Production verification

1. Confirm `/health` reports both API and database healthy.
2. Confirm `/api/news` returns at most three safe public records, newest first.
3. Verify Telegram `/start`, authorization, create/edit/archive/restore, and real Cloudinary media.
4. Publish A-E and verify `A`; `B,A`; `C,B,A`; `D,C,B`; `E,D,C`.
5. Confirm the deployed website changes without a frontend redeploy.
6. Submit a real lead and confirm Telegram delivery plus a `delivered` database row.

Do not report Telegram live-message checks as passed until the administrator has started the bot.
