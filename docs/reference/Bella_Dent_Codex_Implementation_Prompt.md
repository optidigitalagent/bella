# CODEX IMPLEMENTATION PROMPT — Bella Dent «Життя клініки» + Telegram CMS + Leads

Ты работаешь как senior full-stack engineer / integration engineer. Твоя задача — расширить уже существующий production-сайт Bella Dent, не переделывая его с нуля и не ломая текущую визуальную систему, прайс, врачей, SEO, GitHub Pages и кастомный домен.

## 0. Исходные материалы

Репозиторий:
- https://github.com/optidigitalagent/bella

Production domain:
- https://belladentclinik.kr.ua/

GitHub Pages fallback:
- https://optidigitalagent.github.io/bella/

В корень/папку docs/reference проекта я передам два обязательных файла:
- `Bella_Dent_Clinic_Life_Telegram_Brief.md` — главный функциональный/архитектурный brief.
- `Bella_Dent_Clinic_Life_Visual_Reference.png` — обязательный visual reference секции «Життя клініки».

Сначала прочитай brief ПОЛНОСТЬЮ. Не начинай реализацию до завершения аудита текущего репозитория и понимания brief.

## 1. Что уже есть в проекте и что нельзя сломать

Это существующий статический сайт Bella Dent на GitHub Pages с кастомным доменом. В репозитории уже есть:
- `index.html` — основной frontend;
- `price.html`;
- `prices.js`;
- `sheets-loader.js`;
- существующие папки с doctors/cases/certificates/images;
- `CNAME` с production domain.

`sheets-loader.js` уже получает прайс и врачей из Google Sheets через публичный CSV/GViz endpoint. НЕ переписывай этот рабочий механизм без объективной необходимости. Новую CMS новостей реализуй независимо через Railway backend/API.

Нельзя:
- ломать текущий дизайн;
- менять существующий прайс/врачей без необходимости;
- удалять CNAME;
- хранить секреты во frontend/GitHub;
- хранить пользовательские фото/видео новостей в репозитории;
- делать redeploy сайта при каждой новости;
- строить публикацию через GitHub commit/news.json;
- парсить Instagram как источник данных;
- заявлять задачу завершённой без реального E2E-теста, если доступны credentials.

## 2. Перед кодом — обязательный audit

Сделай сначала audit и коротко зафиксируй его в `docs/clinic-life-implementation-notes.md`:

1. `git status`, текущая ветка, незакоммиченные изменения.
2. Точный способ деплоя GitHub Pages.
3. Структура `index.html` и существующие секции.
4. Где находится секция отзывов — новая секция «Життя клініки» должна быть вставлена НЕПОСРЕДСТВЕННО ПЕРЕД текущей секцией отзывов, как на visual reference.
5. Текущие design tokens: цвета, шрифты, container widths, radii, shadows, buttons, spacing, breakpoints.
6. Существующие формы/CTA: если уже есть подходящая форма записи, подключи её к Lead API вместо создания дубликата. Если подходящей формы нет — добавь минимальную форму в существующий дизайн.
7. Существующие JS-зависимости и pattern подключения скриптов.
8. Убедись, что `sheets-loader.js` продолжит работать после изменений.

Если рабочая копия грязная и изменения не относятся к задаче — НЕ перетирай их. Зафиксируй и остановись с понятным отчётом.

## 3. Общая архитектура, которую нужно реализовать

Внешний UX:

```text
Сотрудник Bella Dent
  ↓
Telegram Bot
  ↓
Railway Backend / Orchestrator
  ↓
Cloudinary (media)
  ↓
Google Sheets (content DB)
  ↓
GET /api/news
  ↓
Bella Dent website
```

Параллельно:

```text
Bella Dent website form
  ↓
POST /api/leads
  ↓
Railway Backend
  ↓
Telegram Bot API
  ↓
администраторы Bella Dent
```

Основная версия не должна зависеть от OpenAI/LLM. Это deterministic automation. AI-функции можно оставить как future extension, но не подключать в MVP.

## 4. Рекомендуемая структура новой backend-части

Не обязательно дословно, но архитектурно раздели систему на модули. Предпочтительно создать внутри этого же repo папку `server/`, чтобы frontend оставался GitHub Pages, а `server/` разворачивался отдельным Railway service.

Пример:

```text
server/
  package.json
  .env.example
  railway.json (если нужен)
  src/
    index.mjs
    config.mjs
    bot/
      telegram.mjs
      state.mjs
      handlers.mjs
    routes/
      news.mjs
      leads.mjs
      telegram-webhook.mjs
      health.mjs
    services/
      cloudinary.mjs
      google-sheets.mjs
      news-service.mjs
      leads-service.mjs
    lib/
      validation.mjs
      sanitize.mjs
      logger.mjs
      mutex.mjs
  scripts/
    init-sheets.mjs
    set-telegram-webhook.mjs
  test/
    ...
```

Рекомендуемый стек backend:
- Node.js 20+;
- Express или Fastify (выбери одно и обоснуй минимально);
- официальный Cloudinary SDK;
- `googleapis` для Google Sheets;
- Zod (или эквивалент) для validation;
- `helmet`/безопасные HTTP headers;
- CORS allowlist;
- rate limiting;
- built-in `fetch` для Telegram file download;
- тестовый runner Node/Vitest/Jest — выбери один, не создавай тяжёлую инфраструктуру без причины.

## 5. Telegram Bot — меню и доступ

Bot доступен ТОЛЬКО whitelist admin IDs.

После `/start`:

```text
Bella Dent — управління сайтом

[ ➕ Додати новину ]
[ 📰 Активні новини ]
[ 📁 Архів ]
```

Любой Telegram ID, которого нет в `TELEGRAM_ADMIN_IDS`, не получает CMS-доступ. Ответ — нейтральный отказ без утечки информации.

Production Telegram должен работать через webhook на публичный Railway URL.

Webhook обязательно защищать `TELEGRAM_WEBHOOK_SECRET` и проверкой `X-Telegram-Bot-Api-Secret-Token`.

## 6. Flow добавления новости

State machine минимум:

```text
IDLE
WAITING_TITLE
WAITING_DESCRIPTION
WAITING_MEDIA
WAITING_INSTAGRAM
WAITING_CONFIRMATION
```

Сценарий:

1. `➕ Додати новину`
2. Bot: `Надішліть заголовок новини.`
3. Пользователь отправляет title.
4. Bot: `Тепер надішліть опис новини.`
5. Пользователь отправляет description.
6. Bot: `Надішліть фотографію або відео.`
7. Пользователь отправляет media.
8. Backend скачивает Telegram file и загружает в Cloudinary.
9. Bot: `Надішліть посилання на Instagram-публікацію або натисніть «Пропустити».`
10. Preview:

```text
Перевірте новину:

Заголовок:
...

Опис:
...

Медіа:
✅ завантажено

Instagram:
✅ додано / —

[ ✅ Опублікувати ]
[ ✏️ Змінити ]
[ ❌ Скасувати ]
```

11. НИЧЕГО не публиковать до `✅ Опублікувати`.
12. `❌ Скасувати` очищает draft state. Если media уже загружено в Cloudinary, аккуратно удалить orphan asset либо предусмотреть cleanup policy.

Draft state для MVP может быть in-memory с TTL, потому что draft не является опубликованной записью. При restart допускается потеря незавершённого draft, но это должно быть безопасно: никакая частичная новость не должна попасть на сайт. Документируй это. Если легко сделать устойчивее без лишней инфраструктуры — можно сохранять draft metadata отдельно, но не усложняй MVP без причины.

## 7. Media pipeline / Cloudinary

При получении media:

```text
Telegram file_id
→ getFile
→ download
→ validate type/size
→ Cloudinary upload
→ secure_url
→ public_id
→ draft metadata
```

Поддержать минимум:
- Telegram photo;
- Telegram video;
- при необходимости image/video document, если MIME валиден.

Не принимать произвольные файлы.

Использовать Cloudinary folder, например:
- `bella-dent/news`

Сохранять:
- `media_type` (`image`/`video`);
- `media_url`;
- `cloudinary_public_id`.

Frontend не хранит media locally.

Для изображений использовать Cloudinary delivery с auto format/quality там, где это безопасно (`f_auto`, `q_auto`) и responsive behavior. Для видео — корректный Cloudinary delivery без autoplay со звуком.

Размер файлов ограничить через env/config (`MAX_MEDIA_BYTES`), значение по умолчанию выбрать консервативно и задокументировать.

## 8. Google Sheets как CMS

Использовать один spreadsheet, минимум листы:
- `News`
- `Leads`

Добавить `scripts/init-sheets.mjs`, который безопасно создаёт/проверяет headers и не уничтожает существующие данные.

### `News` headers

Используй как минимум:

```text
id
status
published_at
updated_at
archived_at
title
description
media_type
media_url
cloudinary_public_id
instagram_url
created_by_telegram_id
publish_request_id
```

Statuses:
- `draft` (если решишь сохранять drafts; необязательно для основного flow)
- `published`
- `archived`

`deleted` — только если реально понадобится, не путать с archive.

### `Leads` headers

```text
id
created_at
name
phone
comment
source
status
```

Можно добавить technical columns (`ip_hash`, `user_agent`) только если это оправдано и без хранения лишних персональных данных.

## 9. КРИТИЧЕСКОЕ правило rolling window = 3

На сайте НИКОГДА не должно быть больше трёх `published` news.

Acceptance sequence:

```text
A → сайт: A
B → сайт: B,A
C → сайт: C,B,A
D → сайт: D,C,B + A archived
E → сайт: E,D,C + B archived
```

При publish:

1. Сгенерировать unique news ID.
2. Зафиксировать UTC timestamp.
3. Идемпотентно обработать callback/publish request.
4. Создать/записать news row как `published`.
5. Прочитать все `published`.
6. Отсортировать `published_at DESC`.
7. Всё после первых трёх перевести в `archived` (обычно это одна самая старая запись).
8. После mutation ЕЩЁ РАЗ прочитать Sheet и assert:
   - `published.length <= 3`;
   - первые 3 соответствуют ожидаемому порядку.
9. Только после успешной проверки ответить пользователю `✅ Новину опубліковано`.

Не сообщать success до фактической записи и проверки.

### Concurrency / idempotency

Google Sheets не транзакционен. Для MVP Railway service должен работать в одном replica/process и использовать publish mutex + `publish_request_id`, чтобы двойной callback или двойной клик не создавал дубликаты.

Если `publish_request_id` уже был обработан — вернуть предыдущий результат, не публиковать повторно.

## 10. Управление активными новостями

`📰 Активні новини` показывает максимум 3:

```text
1. ...
2. ...
3. ...
```

Для выбранной новости:
- `✏️ Змінити`
- `📁 Архівувати`
- `⬅️ Назад`

Редактирование минимум:
- title;
- description;
- Instagram URL;
- media (можно заменить через новый upload).

При замене media старый Cloudinary asset не удалять до успешного сохранения нового. После успешного update старый asset можно удалить безопасно.

Архивирование немедленно убирает новость из `/api/news`.

## 11. Архив

`📁 Архів` показывает старые записи постранично/небольшими batch, чтобы не спамить Telegram.

Минимум:
- открыть запись;
- посмотреть metadata;
- `♻️ Відновити` (желательно).

Restore должен снова применить rolling-window rule: восстановленная запись становится published с новым `published_at` (или отдельно согласованной логикой), и если published > 3 — самая старая активная уходит в архив.

## 12. News API

Endpoint:

```http
GET /api/news
```

Возвращает только `status=published`, максимум 3, `published_at DESC`.

JSON shape:

```json
[
  {
    "id": "n004",
    "title": "...",
    "description": "...",
    "mediaType": "image",
    "mediaUrl": "https://res.cloudinary.com/...",
    "instagramUrl": "https://www.instagram.com/...",
    "publishedAt": "2026-08-11T08:00:00.000Z"
  }
]
```

Не отдавать frontend:
- `cloudinary_public_id`;
- Telegram IDs;
- internal status fields;
- service credentials.

Для MVP используй `Cache-Control: no-store` либо очень короткий безопасный cache, чтобы публикация была видна без redeploy и без заметной задержки.

При ошибке Google Sheets API endpoint возвращает корректный 5xx JSON, логирует technical error server-side и не раскрывает secrets.

## 13. Visual reference секции «Життя клініки»

Файл:
- `Bella_Dent_Clinic_Life_Visual_Reference.png`

Он является ОБЯЗАТЕЛЬНЫМ visual reference.

На screenshot:
- существующий Bella Dent header;
- eyebrow: `ЖИТТЯ КЛІНІКИ`;
- heading: `Новини та події Bella Dent`;
- светлый/ivory фон Bella Dent;
- карточка с большим media;
- дата;
- serif title;
- description;
- outlined gold CTA `ЧИТАТИ БІЛЬШЕ`;
- carousel dots;
- после этой секции начинается `ВІДГУКИ / Відгуки наших пацієнтів`.

Не создавай новую дизайн-систему. Сначала вытащи реальные tokens из `index.html` (`--ivory`, `--cream`, `--gold`, `--brown`, serif/sans, radii, shadows и т.д.) и переиспользуй их.

### Место секции

Вставить непосредственно ПЕРЕД существующей секцией отзывов.

### Copy

Eyebrow:
- `ЖИТТЯ КЛІНІКИ`

Heading:
- `Новини та події Bella Dent`

Можно добавить очень короткий intro только если он не ломает reference; не нужен шаблонный маркетинговый текст.

### Desktop

На широком desktop при 3 news:
- `news[0]` — featured large card слева;
- `news[1]` — справа сверху;
- `news[2]` — справа снизу;
- визуальный вес примерно 58/42;
- сохранить Bella Dent spacing/radius/typography.

При 1 news — одна featured card без пустых fake cards.
При 2 — featured + одна secondary.
При 0 — секцию скрыть полностью.

### Mobile

На mobile максимально следовать screenshot:
- одна карточка в viewport;
- свайп/горизонтальный carousel между максимум 3 news;
- dots снизу (1–3);
- нормальный touch interaction;
- без horizontal overflow страницы;
- карточка ~100% доступной ширины с существующими отступами Bella Dent;
- media сверху, затем date/title/description/CTA.

Не делать тяжёлую carousel library, если можно реализовать небольшим vanilla JS/CSS.

### Card behavior

Поля:
- media;
- date;
- title;
- description;
- Instagram link (если есть).

Date отображать по-украински, например `15 червня 2026`.

Description clamp:
- mobile/secondary: 2–4 строки;
- featured: по визуальному балансу.

`ЧИТАТИ БІЛЬШЕ`:
- если `instagramUrl` есть — открыть Instagram в новой вкладке `target="_blank" rel="noopener noreferrer"`;
- если Instagram нет, но description обрезан — кнопка может раскрыть полный текст/открыть лёгкий modal/details;
- если читать больше нечего — кнопку скрыть.

Image:
- `<img loading="lazy" decoding="async">`;
- `object-fit: cover`;
- без layout shift (width/height/aspect-ratio).

Video:
- `playsinline`;
- controls или лёгкий play interaction;
- НЕ autoplay со звуком;
- не ломает размер карточки.

### Loading/error state

При загрузке API:
- skeleton с теми же пропорциями, без layout jump.

Если API упал:
- не ломать страницу;
- скрыть news section или показать только production-safe fallback без fake news;
- console/log error;
- не оставлять `undefined`/broken image.

## 14. Website API config

Не хардкодить Railway URL в десятке мест.

Добавь один frontend config point, например:

```js
window.BELLA_API_BASE = 'https://...railway.app';
```

или отдельный маленький `site-config.js`.

Сделай так, чтобы Railway URL можно было заменить в одном месте.

Production CORS должен разрешать минимум:
- `https://belladentclinik.kr.ua`
- при необходимости GitHub Pages preview `https://optidigitalagent.github.io`

Через env поддержать `ALLOWED_ORIGINS`.

## 15. Leads API и форма

Endpoint:

```http
POST /api/leads
Content-Type: application/json
```

Payload минимум:

```json
{
  "name": "Анна",
  "phone": "+380...",
  "comment": "Хочу записатися на консультацію",
  "website": ""
}
```

`website` — honeypot: реальный пользователь его не видит/не заполняет. Если заполнен — silently reject/204 либо safe response без отправки Telegram.

Validation:
- name required, разумный max length;
- phone required, разумный max length;
- comment optional, max length;
- trim + sanitization;
- JSON body limit;
- rate limit по IP;
- CORS only allowlist.

После валидной заявки отправить каждому `TELEGRAM_ADMIN_IDS`:

```text
🔔 НОВА ЗАЯВКА З САЙТУ

Імʼя:
Анна

Телефон:
+380...

Коментар:
Хочу записатися на консультацію

Дата:
...
```

Затем append в `Leads` sheet.

Порядок должен быть fail-safe:
- если Telegram не доставлен — frontend не должен получать fake success;
- можно сначала записать Lead и затем Telegram, но response success только после выполнения выбранного критерия; документируй решение.

Frontend success показывать ТОЛЬКО после реального 2xx backend response.

Не использовать `setTimeout`/локальный fake success.

Если на текущем сайте уже есть форма записи — подключи именно её, не делай дубликат. Если нет — создай минимальную форму `Імʼя`, `Телефон`, `Коментар` в существующей CTA/contact area.

## 16. Security

Обязательно:
- Telegram whitelist;
- Telegram webhook secret;
- Cloudinary secret только backend;
- Google service account только backend;
- env secrets только Railway Variables;
- `.env` в `.gitignore`;
- `.env.example` без значений;
- CORS allowlist;
- rate limiting для leads и webhook routes;
- input validation;
- text sanitization/escaping;
- URL validation для Instagram (`https://instagram.com/`, `https://www.instagram.com/`);
- media MIME/type validation;
- media max size;
- Cloudinary/Sheets/Telegram error handling;
- no secrets in logs;
- idempotent publish;
- no XSS from title/description (рендерить через `textContent`, не unsafe innerHTML).

## 17. Environment variables

Сделай `.env.example` как минимум:

```env
NODE_ENV=development
PORT=3000
PUBLIC_BASE_URL=
SITE_ORIGIN=https://belladentclinik.kr.ua
ALLOWED_ORIGINS=https://belladentclinik.kr.ua,https://optidigitalagent.github.io

TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_IDS=
TELEGRAM_WEBHOOK_SECRET=

CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CLOUDINARY_FOLDER=bella-dent/news
MAX_MEDIA_BYTES=20000000

GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
# или поддержи GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=
NEWS_SHEET_NAME=News
LEADS_SHEET_NAME=Leads

LEAD_RATE_LIMIT_WINDOW_MS=900000
LEAD_RATE_LIMIT_MAX=5
```

Если Railway плохо работает с raw JSON, реализуй поддержку base64 service-account env и опиши её.

## 18. Railway

Backend — отдельный Railway service из `server/`.

Нужно:
- health endpoint `GET /health`;
- bind на `process.env.PORT`;
- production webhook Telegram;
- startup без polling conflict;
- понятные logs;
- graceful shutdown;
- не выводить secrets.

Добавь README/setup:
1. как создать Telegram bot через BotFather;
2. как узнать Telegram user IDs администраторов;
3. как создать Cloudinary credentials;
4. как создать Google service account;
5. как share spreadsheet на service account email;
6. как задать Railway Variables;
7. как deploy `server/` в Railway;
8. как вызвать script set-webhook;
9. как установить frontend API base URL;
10. как проверить `/health` и `/api/news`.

## 19. Тесты — обязательны

Добавь unit/integration tests минимум для:

### News rolling logic
- publish A => A
- publish B => B,A
- publish C => C,B,A
- publish D => D,C,B and A archived
- publish E => E,D,C and B archived

### Idempotency
- одинаковый `publish_request_id` дважды => одна news.

### API
- `GET /api/news` возвращает max 3, правильный order, без internal fields.

### Validation
- invalid Instagram URL reject;
- invalid/oversize media reject;
- lead missing phone reject;
- honeypot не отправляется в Telegram;
- unauthorized Telegram ID не имеет CMS access.

### Error handling
- Cloudinary error не создаёт published news;
- Sheets error не сообщает Telegram success;
- Telegram lead delivery error не показывает frontend fake success.

Внешние API в unit/integration тестах mock/fake adapters. Не совершай реальные публикации из обычного test suite.

## 20. Browser QA

Обязательно проверить frontend на:
- 360px
- 390px
- 430px
- 768px
- 1024px
- 1280px
- 1440px

Проверить:
- header не сломан;
- news section перед reviews;
- mobile carousel и dots;
- images/videos;
- no horizontal overflow;
- form UX;
- price page и doctors loading не сломаны;
- существующая навигация продолжает работать;
- custom domain assumptions не нарушены.

Если есть возможность — Playwright. Если в repo нет Node frontend tooling, можно добавить lightweight QA tooling отдельно, не превращая сайт в framework migration.

НЕ мигрировать весь статический сайт в React/Vue/Next только ради этой задачи.

## 21. E2E acceptance — НЕ ИМИТИРОВАТЬ

После локальных тестов и если реальные credentials доступны, выполнить настоящий сценарий:

1. Telegram admin `/start`.
2. Добавить A с реальным test image/video.
3. Убедиться: media в Cloudinary.
4. Убедиться: row в Google Sheets.
5. Убедиться: `/api/news` возвращает A.
6. Убедиться: website реально показывает A без redeploy.
7. Повторить B, C, D, E.
8. Проверить:

```text
A
B,A
C,B,A
D,C,B + A archived
E,D,C + B archived
```

9. Проверить `Активні новини` в Telegram.
10. Проверить archive.
11. Проверить edit.
12. Отправить test lead с сайта и убедиться, что Telegram admin реально получил её.
13. Проверить row в `Leads`.

Если credentials отсутствуют — НЕ пиши «готово». Напиши статус:

```text
IMPLEMENTATION_COMPLETE_BUT_LIVE_E2E_BLOCKED
```

и перечисли ровно какие credentials/variables нужны пользователю для финальной проверки.

## 22. Git / change safety

Не пушить, не merge и не deploy без отдельного явного разрешения пользователя.

Работать в feature branch, например:
- `feat/clinic-life-telegram-cms`

Перед изменениями:
- сохранить baseline `git status`;
- не трогать unrelated files;
- не удалять текущий SEO/content;
- не коммитить credentials;
- не добавлять generated heavy media.

После реализации:
- `git diff --check`;
- тесты;
- browser QA;
- security review;
- список изменённых файлов.

## 23. Что я хочу получить от тебя в финале

Не просто «готово», а точный отчёт:

### A. Audit
- что нашёл в текущем сайте;
- где вставил news section;
- какая существующая форма была переиспользована/создана.

### B. Implementation
- frontend files changed;
- backend files added;
- Google Sheet schema;
- Telegram commands/menu;
- API endpoints.

### C. Tests
Покажи команды и результаты:
- unit/integration;
- browser QA;
- `git diff --check`;
- security/static checks.

### D. Live E2E
Отдельно:
- Telegram -> Cloudinary: PASS/FAIL/BLOCKED
- Cloudinary -> Sheets: PASS/FAIL/BLOCKED
- Sheets -> `/api/news`: PASS/FAIL/BLOCKED
- `/api/news` -> website: PASS/FAIL/BLOCKED
- D archives A: PASS/FAIL/BLOCKED
- E archives B: PASS/FAIL/BLOCKED
- website lead -> Telegram: PASS/FAIL/BLOCKED

### E. Deployment/setup
- exact Railway Variables;
- exact commands;
- webhook URL;
- API base URL;
- Sheet initialization command;
- что пользователь должен сделать вручную.

### F. Safety
- confirm no secrets committed;
- confirm no news media committed;
- confirm current price/doctors Google Sheets functionality still works;
- confirm current site visual/SEO not regressed.

## 24. Definition of Done

Задача считается полностью завершённой ТОЛЬКО если:

- существующий Bella Dent сайт не сломан;
- «Життя клініки» визуально соответствует provided reference и дизайн-системе Bella Dent;
- max 3 active news;
- 4-я/старейшая автоматически archived;
- news добавляются без code change/redeploy;
- Telegram admin flow работает;
- Cloudinary хранит media;
- Google Sheets хранит news;
- Railway отдаёт `/api/news`;
- website получает news через API;
- form отправляет реальную заявку через Railway в Telegram;
- security controls включены;
- tests зелёные;
- browser QA зелёный;
- live E2E фактически пройден либо честно помечен BLOCKED из-за отсутствующих credentials.

Не сокращай scope и не заменяй реальные интеграции фейковыми mock-success в production code.
