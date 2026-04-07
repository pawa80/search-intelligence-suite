-- Migration 011: Add page_elements JSONB column to pages table
-- Persists structured crawl data (H2s, OG tags, JSON-LD, hero alt, referrer, crawl time)
-- so the persistent view shows the same data as the active crawl view.

ALTER TABLE pages ADD COLUMN IF NOT EXISTS page_elements JSONB DEFAULT '{}';
COMMENT ON COLUMN pages.page_elements IS 'Structured crawl data: h2_structure, og_tags, json_ld, hero_image_alt, referrer, crawl_time_seconds. Persisted on every crawl.';

-- Reload PostgREST schema cache
NOTIFY pgrst, 'reload schema';
