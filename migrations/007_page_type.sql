-- Add page type column for smarter arbeidspakke generation
ALTER TABLE pages ADD COLUMN page_type TEXT DEFAULT NULL;
