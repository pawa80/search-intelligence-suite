-- Migration 009: Add model_tier and model_name columns to usage_events
-- Run in Supabase SQL editor. After running, reload PostgREST schema:
-- Supabase Dashboard → Settings → API → "Reload Schema"

ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS model_tier TEXT;
ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS model_name TEXT;
