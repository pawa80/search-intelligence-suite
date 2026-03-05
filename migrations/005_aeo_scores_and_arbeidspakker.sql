-- Migration: Create aeo_scores and arbeidspakker tables

-- Stores AEO audit scores per page
CREATE TABLE aeo_scores (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  citation_rate FLOAT,
  entity_coverage_score INTEGER CHECK (entity_coverage_score BETWEEN 0 AND 100),
  answerability_score INTEGER CHECK (answerability_score BETWEEN 0 AND 100),
  structure_score INTEGER CHECK (structure_score BETWEEN 0 AND 100),
  overall_aeo_score INTEGER CHECK (overall_aeo_score BETWEEN 0 AND 100),
  analysed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(page_id)
);

-- Stores generated arbeidspakker
CREATE TABLE arbeidspakker (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  page_id UUID NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  intent TEXT,
  arbeidspakke_markdown TEXT,
  context_snapshot JSONB,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE aeo_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE arbeidspakker ENABLE ROW LEVEL SECURITY;

CREATE POLICY "aeo_scores_user_access" ON aeo_scores
  FOR ALL USING (user_owns_project(project_id));

CREATE POLICY "arbeidspakker_user_access" ON arbeidspakker
  FOR ALL USING (user_owns_project(project_id));
