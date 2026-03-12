-- Usage event tracking for all API calls and app analytics
CREATE TABLE usage_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    project_id UUID REFERENCES projects(id),
    event_type TEXT NOT NULL,
    event_detail TEXT,
    api_provider TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost_usd NUMERIC(10, 6),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_usage_events_user ON usage_events(user_id);
CREATE INDEX idx_usage_events_project ON usage_events(project_id);
CREATE INDEX idx_usage_events_type ON usage_events(event_type);
CREATE INDEX idx_usage_events_created ON usage_events(created_at);

ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;

-- Any authenticated user can INSERT their own events
CREATE POLICY usage_events_insert ON usage_events FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can only read their own events
CREATE POLICY usage_events_select ON usage_events FOR SELECT
    USING (user_id = auth.uid());
