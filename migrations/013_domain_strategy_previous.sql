-- Migration 013: Add domain_strategy_previous backup column
-- Safety net: stores the previous strategy before overwrite
ALTER TABLE projects ADD COLUMN IF NOT EXISTS domain_strategy_previous JSONB DEFAULT '{}';
COMMENT ON COLUMN projects.domain_strategy_previous IS 'Backup of previous domain_strategy before regeneration. Safety net against timeout/failure overwrites.';

-- Reload PostgREST schema cache
NOTIFY pgrst, 'reload schema';
