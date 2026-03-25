from __future__ import annotations
from supabase import create_client, Client
from api.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not settings.has_db:
            raise RuntimeError("Supabase not configured — set SUPABASE_URL and SUPABASE_SERVICE_KEY")
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


async def save_analysis(
    user_id: str,
    file_name: str,
    file_format: str,
    result: dict,
) -> dict:
    """Save a full analysis result to Supabase."""
    db = get_supabase()

    scores = result.get("db_scores", {})
    top_db, top_score = None, None
    if scores:
        top = list(scores.items())[0]
        top_db = top[0]
        top_score = top[1].get("absolute_pct")

    table_count = result.get("schema_summary", {}).get("tables", 0)

    row = {
        "user_id":     user_id,
        "file_name":   file_name,
        "file_format": file_format,
        "top_db":      top_db,
        "top_score":   top_score,
        "table_count": table_count,
        "result":      result,
    }

    response = db.table("analyses").insert(row).execute()
    return response.data[0] if response.data else {}


async def get_user_history(user_id: str, limit: int = 20) -> list:
    """Get a user's past analyses — summary only, no full result blob."""
    db = get_supabase()
    response = (
        db.table("analyses")
        .select("id, file_name, file_format, top_db, top_score, table_count, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_analysis_by_id(analysis_id: str, user_id: str) -> dict | None:
    """Get a single full analysis — only if it belongs to this user."""
    db = get_supabase()
    response = (
        db.table("analyses")
        .select("*")
        .eq("id", analysis_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    return response.data if response.data else None


async def delete_analysis(analysis_id: str, user_id: str) -> bool:
    """Delete an analysis — only if it belongs to this user."""
    db = get_supabase()
    response = (
        db.table("analyses")
        .delete()
        .eq("id", analysis_id)
        .eq("user_id", user_id)
        .execute()
    )
    return bool(response.data)


async def get_user_stats(user_id: str) -> dict:
    """Get summary stats for the dashboard header."""
    db = get_supabase()
    response = (
        db.table("analyses")
        .select("file_format, top_db")
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []
    total = len(rows)

    formats = {}
    dbs = {}
    for r in rows:
        f = r.get("file_format", "sql")
        formats[f] = formats.get(f, 0) + 1
        d = r.get("top_db")
        if d:
            dbs[d] = dbs.get(d, 0) + 1

    fav_format = max(formats, key=formats.get) if formats else "sql"
    fav_db     = max(dbs,     key=dbs.get)     if dbs     else None

    return {
        "total_analyses": total,
        "favourite_format": fav_format,
        "favourite_db": fav_db,
    }