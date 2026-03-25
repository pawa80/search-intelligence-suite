-- Allow project owners to update their projects (e.g. domain_context)
-- Uses user_in_workspace() SECURITY DEFINER to check workspace membership
CREATE POLICY projects_update ON projects
    FOR UPDATE
    USING (user_in_workspace(workspace_id))
    WITH CHECK (user_in_workspace(workspace_id));
