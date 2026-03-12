-- Save intent per page + domain-level universal context for arbeidspakker
ALTER TABLE pages ADD COLUMN intent TEXT DEFAULT NULL;
ALTER TABLE projects ADD COLUMN domain_context TEXT DEFAULT NULL;
