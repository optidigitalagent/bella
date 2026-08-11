# Bella Dent — Clinic Life implementation notes

## Baseline audit (2026-08-11)

- Repository: `https://github.com/optidigitalagent/bella.git`.
- Baseline commit: `e19dcbb` (`main`, equal to `origin/main`).
- Baseline worktree: only `docs/` was untracked. It contains the task reference Markdown files and is task-related; no unrelated local edits were present.
- Working branch created for implementation: `feat/clinic-life-telegram-cms`.
- GitHub Pages is configured as a legacy Pages build from `main` at repository root (`/`), with HTTPS enforced.
- Production custom domain is preserved in `CNAME`: `belladentclinik.kr.ua`.
- GitHub Pages fallback is `https://optidigitalagent.github.io/bella/`.

## Required references

- Read in full: `docs/reference/Bella_Dent_Codex_Implementation_Prompt.md` (primary implementation contract).
- Read in full: `docs/reference/Bella_Dent_Clinic_Life_Telegram_Brief.md` (business and integration brief).
- `docs/reference/Bella_Dent_Clinic_Life_Visual_Reference.png` is not present anywhere in the workspace and is not tracked on `origin/main`. The implementation therefore follows the reference description embedded in the primary contract (ivory section, eyebrow, serif heading, large media card, date, outlined gold CTA, mobile carousel dots), but pixel-level comparison with the missing PNG is blocked until that file is supplied.

## Existing frontend architecture

- Static, framework-free GitHub Pages site.
- `index.html` contains all homepage markup, core CSS, and most interactive JavaScript.
- Homepage section order before this change: `#home`, `#services`, `#about`, `#certificates`, `#doctors`, `#cases`, `#reviews`, `#contacts`, map, footer.
- The existing reviews section begins at `#reviews`; Clinic Life must be inserted between the closing `#cases` section and `#reviews`.
- `price.html` is a separate static price page.
- `prices.js` provides static price fallback data.
- `sheets-loader.js` independently reads public Google Sheets CSV/GViz data for `ПРАЙС` and `ЛІКАРІ`. It exposes `window.SheetsLoader`; the homepage keeps static doctors as fallback. This loader will not be modified by Clinic Life.
- Existing dependencies are only browser-native APIs and Google Fonts. There is no frontend framework or bundler.

## Existing design tokens and responsive baseline

- Colors: `--ivory #FBF7F1`, `--cream #F4EDE3`, `--beige #EFE4D6`, `--gold #C49A55`, `--gold-light #D0A96A`, `--gold-dark #B88A44`, `--brown #1F1A16`, `--brown-mid #3A2D24`, `--gray-brown #6F6258`, `--footer-bg #15100B`.
- Type: `Cormorant Garamond` serif headings and `Jost` sans-serif body/UI.
- Radius: `12px` cards; header/buttons also use thin square/near-square outlined styling.
- Container: max width `1440px`, horizontal padding `80px`; `32px` at <=900px and `20px` at <=600px.
- Section spacing: `100px` desktop, `64px` at <=600px.
- Typical card shadow: `0 2px 20px rgba(31,26,22,0.07)`; hover shadow/translate is used on cards.
- Existing breakpoints: 1200px, 900px, and 600px (certificate logic also uses 640/1024 in JS).
- Section eyebrow: 10px uppercase, 3px letter spacing, gold. Section heading: serif `clamp(36px, 4vw, 54px)`.

## Existing reviews, forms, and CTAs

- Reviews are an inline vanilla-JS carousel in `#reviews`, showing two cards above 600px and one on mobile with arrow/dot/touch controls.
- There is no existing HTML form.
- Header, hero, and footer booking CTAs point to `#contacts`; `#contacts` is therefore the appropriate existing conversion area for one minimal lead form rather than creating a duplicate section.
- The new form will use the existing typography, gold outline/button treatment, cream contact card, and will only show success after a real 2xx response from the Railway backend.

## Target architecture

```text
Telegram admin -> protected Railway webhook -> deterministic state machine
               -> Telegram file download -> Cloudinary
               -> PostgreSQL News repository -> transactional rolling published window (3)
               -> GET /api/news -> vanilla-JS Clinic Life renderer

Website lead form -> POST /api/leads -> PostgreSQL Leads audit row
                  -> Telegram delivery to every configured admin
                  -> delivered status and success only after confirmed delivery
```

The frontend will retain one API configuration point in `site-config.js`. All Telegram, Google, and Cloudinary credentials remain server-side as Railway Variables. The backend will use Express on Node.js 20+, Zod validation, Helmet, explicit CORS allowlisting, rate limiting, a single-process publish mutex, and adapter-driven services that can be tested with fakes.

## Key invariants

- `/api/news` exposes only safe public fields, newest first, maximum three.
- Publishing is idempotent by a unique `publish_request_id` and serialized across replicas by a PostgreSQL transaction-scoped advisory lock.
- After every publish/restore, all published rows after the newest three are archived and verified inside the same database transaction before Telegram receives success.
- Drafts are in memory with TTL. A restart may discard a draft, but can never publish it. Uploaded draft media is deleted on cancel/expiry where possible.
- Replacing media saves the new record before deleting the old Cloudinary asset.
- One Railway process/replica is required for the MVP mutex guarantee.
- Existing price/doctors CSV/GViz loading remains isolated and unchanged.

## Implemented components

- Frontend: `clinic-life.css`, `clinic-life.js`, and the single Railway origin setting in `site-config.js`.
- `index.html`: Clinic Life inserted immediately before `#reviews`; one lead form added inside the existing `#contacts` card.
- Backend: Express API, security middleware, PostgreSQL repository/versioned migrations, Cloudinary media adapter, Telegram client/CMS state machine, news/lead services, webhook setup script, and Railway config under `server/`.
- Telegram CMS: add with preview/confirm/cancel; active list; edit title/description/Instagram/media; archive; paginated archive; restore.
- Tests: rolling A–E acceptance, idempotency, public API shape, lead/honeypot behavior, Telegram whitelist/webhook secret, media and URL validation, and upstream-failure behavior.
- Browser QA specification: `server/qa/browser.spec.mjs` covers 360, 390, 430, 768, 1024, 1280, and 1440 px via projects in `server/playwright.config.mjs`.

## Verification status at implementation handoff

- Node unit/integration tests: 16/16 passing.
- Node coverage run: passing; aggregate line coverage 69.78%.
- `npm audit --omit=dev`: 0 vulnerabilities.
- JavaScript/module syntax checks: passing.
- Duplicate homepage IDs: none.
- New frontend unsafe-DOM scan: no `innerHTML`, `insertAdjacentHTML`, `document.write`, or `eval`.
- Credential-shaped value scan: no secrets found.
- `price.html`, `prices.js`, and `sheets-loader.js`: unchanged from baseline.
- Browser execution: blocked because the available browser runtime reported zero browser instances. The QA suite is present but has not been represented as executed.
- Pixel comparison with the required visual PNG: blocked because the PNG is missing from the workspace.
- Live Telegram → Cloudinary → Sheets → API → deployed website and website lead → Telegram: blocked because no real credentials, Railway domain, or deployment authorization were supplied.

## Production continuation (2026-08-11)

- Re-verified branch `feat/clinic-life-telegram-cms` at baseline `c003c8c`, synchronized with `origin`; the worktree was clean before continuation changes.
- Baseline unit/integration suite remained green at 16/16.
- Moved the Telegram webhook rate limiter after the constant-time secret-token check so unauthenticated traffic cannot consume the authenticated webhook budget. Added a regression test; suite is now 17/17.
- Fixed browser QA isolation by moving the dedicated QA server from the commonly occupied port `4173` to configurable port `43917`. The previous configuration could mistake an unrelated SPA fallback for `/health-for-qa` because `reuseExistingServer` was enabled.
- Browser QA executed successfully: 14/14 across 360, 390, 430, 768, 1024, 1280, and 1440 px. Control screenshots at 360, 768, and 1440 px were visually inspected.
- `npm run test:coverage` passes (69.78% aggregate line coverage), `npm audit` reports 0 vulnerabilities, syntax checks pass, `git diff --check` passes, and the credential-shaped value scan passes.
- Created a dedicated Railway project/service (`bella-dent-clinic-life` / `bella-dent-api`) with one replica and generated `https://bella-dent-api-production.up.railway.app`.
- Added non-secret production Variables and generated/stored `TELEGRAM_WEBHOOK_SECRET` directly in Railway without printing it.
- Live deployment remains blocked until the Telegram bot/admin IDs, Cloudinary account credentials, and Google spreadsheet/service-account credentials are supplied securely.

## PostgreSQL architecture change (2026-08-11)

- The prior Google Sheets backend checkpoint is superseded. The production API no longer imports Google libraries, validates Google variables, or reads/writes Sheets.
- Railway PostgreSQL `Postgres` is online in `bella-dent-clinic-life`; `bella-dent-api` uses the native private reference `DATABASE_URL=${{Postgres.DATABASE_URL}}`.
- Versioned migrations create `news`, `leads`, constraints, partial/order indexes, and `schema_migrations` automatically and safely on fresh startup.
- News publish/restore and duplicate lead processing use database transactions plus advisory locks. Rolling A-E, edit, archive, restore, duplicate IDs, delivery failure, and rollback are covered.
- Real Railway PostgreSQL integration passed 24/24 tests in an isolated schema. The temporary public test proxy and test schema were removed afterward; production networking remains private.
- Responsive browser QA passed at 360, 390, 430, 768, 1024, 1280, and 1440 px. Thirteen cases passed in the full run; the sole 1280px teardown timeout passed on focused rerun with the corrected 60-second QA timeout.

## Final production verification (2026-08-11)

- The administrator started the Telegram bot; `/start` and the CMS menu passed.
- Railway reports one running API replica and one running PostgreSQL service. Production `/health` returns `database: ok`; `/api/news` returns 200 with the exact clinic-origin CORS header.
- Telegram webhook URL, reachability, and a zero pending-update queue passed.
- A real Telegram image flowed through Railway into Cloudinary and the resulting delivery URL was reachable.
- The live rolling sequence passed exactly: A; B,A; C,B,A; D,C,B with A archived; E,D,C with B archived.
- Telegram Active News, Archive, Restore, and Edit passed. QA records were archived after verification, leaving the public active window empty.
- GitHub Pages built commit `0f0efa1` successfully from `main`; the custom domain and enforced HTTPS certificate are approved.
- Live rendered QA passed at 390, 768, and 1440 px for the homepage, production API configuration, news visibility, lead form, responsive overflow, and price page.
- A real rendered lead submission passed website -> Railway -> PostgreSQL -> Telegram. Frontend success was shown only after confirmed Telegram delivery.
