from supabase import create_client, Client

from app.config import get_settings


def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("Supabase credentials not configured.")
    return create_client(settings.supabase_url, settings.supabase_key)
