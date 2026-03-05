-- Migration: Create gsc_data table
-- Stores Google Search Console page-level performance data

CREATE TABLE IF NOT EXISTS gsc_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr DOUBLE PRECISION DEFAULT 0,
    position DOUBLE PRECISION DEFAULT 0,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT now(),
    page_id UUID REFERENCES pages(id) ON DELETE SET NULL,
    UNIQUE(project_id, url, date_range_start)
);

-- RLS: reuse existing user_owns_project() SECURITY DEFINER function
ALTER TABLE gsc_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY gsc_data_select ON gsc_data
    FOR SELECT USING (user_owns_project(project_id));

CREATE POLICY gsc_data_insert ON gsc_data
    FOR INSERT WITH CHECK (user_owns_project(project_id));

CREATE POLICY gsc_data_update ON gsc_data
    FOR UPDATE USING (user_owns_project(project_id));

CREATE POLICY gsc_data_delete ON gsc_data
    FOR DELETE USING (user_owns_project(project_id));
