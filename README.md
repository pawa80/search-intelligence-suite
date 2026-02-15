# Search Intelligence Suite

AI search optimisation tools — starting with GEO Tracker.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Copy `.env` and fill in your Supabase credentials (URL + anon key).

3. Run:
   ```
   streamlit run app.py
   ```

## Notes

- Supabase email confirmation may need disabling in the Supabase dashboard (Authentication > Settings > Email Auth) for development/testing.
- Auth uses Supabase Auth. Workspace auto-created on first login.
