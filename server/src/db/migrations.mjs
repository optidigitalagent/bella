export const migrations = [
  {
    version: 1,
    name: 'create_news_and_leads',
    sql: `
      CREATE TABLE news (
        id text PRIMARY KEY,
        status text NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
        published_at timestamptz,
        updated_at timestamptz NOT NULL DEFAULT now(),
        archived_at timestamptz,
        title text NOT NULL,
        description text NOT NULL,
        media_type text NOT NULL CHECK (media_type IN ('image', 'video')),
        media_url text NOT NULL,
        cloudinary_public_id text NOT NULL,
        instagram_url text NOT NULL DEFAULT '',
        created_by_telegram_id text NOT NULL,
        publish_request_id text NOT NULL UNIQUE
      );

      CREATE INDEX news_published_order_idx
        ON news (published_at DESC, id DESC)
        WHERE status = 'published';

      CREATE INDEX news_archive_order_idx
        ON news (archived_at DESC, updated_at DESC, id DESC)
        WHERE status = 'archived';

      CREATE TABLE leads (
        id text PRIMARY KEY,
        created_at timestamptz NOT NULL DEFAULT now(),
        name text NOT NULL,
        phone text NOT NULL,
        comment text NOT NULL DEFAULT '',
        source text NOT NULL,
        status text NOT NULL CHECK (status IN ('received', 'notification_failed', 'delivered')),
        request_id text NOT NULL UNIQUE
      );

      CREATE INDEX leads_created_at_idx ON leads (created_at DESC, id DESC);
      CREATE INDEX leads_status_idx ON leads (status, created_at DESC);
    `
  }
];
