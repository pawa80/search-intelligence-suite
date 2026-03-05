-- Migration: Create crawl_ai_analysis table
-- Stores AI-generated SEO/AEO assessment per crawled page

CREATE TABLE crawl_ai_analysis (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  seo_score INTEGER CHECK (seo_score BETWEEN 0 AND 100),
  aeo_readiness_score INTEGER CHECK (aeo_readiness_score BETWEEN 0 AND 100),
  content_quality_score INTEGER CHECK (content_quality_score BETWEEN 0 AND 100),
  issues JSONB,
  priority_action TEXT,
  action_plan TEXT,
  ai_model TEXT DEFAULT 'llama-3.1-sonar-small-128k-online',
  analysed_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(page_id)
);

ALTER TABLE crawl_ai_analysis ENABLE ROW LEVEL SECURITY;

CREATE POLICY "crawl_ai_analysis_user_access" ON crawl_ai_analysis
  FOR ALL USING (user_owns_project(project_id));
