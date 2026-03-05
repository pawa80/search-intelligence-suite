-- Migration: Create google_connections table
-- Stores OAuth refresh tokens + selected GSC/GA4 properties per user per workspace

CREATE TABLE IF NOT EXISTS google_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    google_refresh_token TEXT NOT NULL,
    google_token_expiry TIMESTAMPTZ,
    gsc_property TEXT,
    ga4_property_id TEXT,
    ga4_property_name TEXT,
    connected_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, user_id)
);

-- RLS: direct user_id check (no SECURITY DEFINER needed)
ALTER TABLE google_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY google_connections_select ON google_connections
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY google_connections_insert ON google_connections
    FOR INSERT WITH CHECK (user_id = auth.uid());

CREATE POLICY google_connections_update ON google_connections
    FOR UPDATE USING (user_id = auth.uid());

CREATE POLICY google_connections_delete ON google_connections
    FOR DELETE USING (user_id = auth.uid());
