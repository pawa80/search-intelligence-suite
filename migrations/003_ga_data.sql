-- Migration: Create ga_data table
-- Stores Google Analytics 4 page-level engagement data

CREATE TABLE IF NOT EXISTS ga_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    page_path TEXT NOT NULL,
    sessions INTEGER DEFAULT 0,
    engaged_sessions INTEGER DEFAULT 0,
    engagement_rate DOUBLE PRECISION DEFAULT 0,
    avg_engagement_time DOUBLE PRECISION DEFAULT 0,
    bounce_rate DOUBLE PRECISION DEFAULT 0,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    page_id UUID REFERENCES pages(id) ON DELETE SET NULL,
    UNIQUE(project_id, page_path, date_range_start)
);

-- RLS: reuse existing user_owns_project() SECURITY DEFINER function
ALTER TABLE ga_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY ga_data_select ON ga_data
    FOR SELECT USING (user_owns_project(project_id));

CREATE POLICY ga_data_insert ON ga_data
    FOR INSERT WITH CHECK (user_owns_project(project_id));

CREATE POLICY ga_data_update ON ga_data
    FOR UPDATE USING (user_owns_project(project_id));

CREATE POLICY ga_data_delete ON ga_data
    FOR DELETE USING (user_owns_project(project_id));
