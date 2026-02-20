-- D1 schema: pageviews and form_submissions for LP analytics
-- Apply with: npx wrangler d1 migrations apply lp-analytics-db --remote

CREATE TABLE IF NOT EXISTS pageviews (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  lp_id       TEXT    NOT NULL,
  referrer    TEXT    DEFAULT '',
  user_agent  TEXT    DEFAULT '',
  tracked_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS form_submissions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  lp_id       TEXT    NOT NULL,
  tracked_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pageviews_lp_id ON pageviews(lp_id);
CREATE INDEX IF NOT EXISTS idx_submissions_lp_id ON form_submissions(lp_id);
