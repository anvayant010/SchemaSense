from __future__ import annotations

from typing import Optional

from api.config import settings


def _build_prompt(analysis: dict) -> str:
    """
    Build a lean, token-efficient prompt for Gemini.
    We pass only the essential facts as plain text — not a JSON dump.
    This keeps input tokens low so output tokens are not starved.
    """
    summary = analysis.get("schema_summary", {})
    quality = analysis.get("quality", {})
    risk = analysis.get("migration_risk", {})
    db_scores = analysis.get("db_scores", {})

    # Top 3 and bottom 2 DBs only
    scores_list = list(db_scores.items())
    top = scores_list[:3]
    bottom = scores_list[-2:]

    key_warnings = []
    for db_name, info in db_scores.items():
        notes = info.get("explanation", {}).get("column_notes", [])
        for n in notes:
            if n.get("severity") == "error":
                key_warnings.append(f"{db_name}: {n['table']}.{n['column']} — {n['issue']}")
        if len(key_warnings) >= 3:
            break

    top_str = ", ".join(f"{db} ({info['absolute_pct']}%)" for db, info in top)
    bottom_str = ", ".join(f"{db} ({info['absolute_pct']}%)" for db, info in bottom)
    warnings_str = "; ".join(key_warnings) if key_warnings else "none"

    migration_notes = []
    for db, info in bottom:
        for w in info.get("explanation", {}).get("migration_warnings", [])[:1]:
            if "no major" not in w.lower():
                migration_notes.append(f"{db}: {w}")

    migration_str = "; ".join(migration_notes) if migration_notes else "none"

    return f"""You are a database migration expert. Write 3-4 sentences advising a developer on their schema analysis results. Be direct and specific.

Schema: {summary.get("tables")} tables, {summary.get("columns")} columns, {summary.get("fks")} foreign keys, types used: {list(summary.get("types", {}).keys())}
Quality score: {quality.get("quality_score")}/10 ({quality.get("quality_label")}), migration risk: {risk.get("risk_level")}
Best fits: {top_str}
Poor fits: {bottom_str}
Key migration issues: {warnings_str}
Migration concerns for poor fits: {migration_str}

Instructions: Name the best DB choice and why. Mention the biggest concrete risk of picking a poor fit (name the specific DB and specific issue). End with one specific actionable step the developer should take next. No bullet points. No generic closing statements like 'we recommend' or 'choose any of'. Complete all sentences."""


def _call_gemini_sync(prompt: str) -> Optional[str]:
    """
    Synchronous Gemini call using the new google-genai SDK.
    Used by worker.py (Celery tasks and sync fallback path).
    """
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=2600,
                temperature=0.3,
            )
        )

        return response.text.strip()

    except Exception as e:
        print(f"[AI] Gemini call failed: {type(e).__name__}: {e}")
        return None


def generate_explanation_sync(analysis: dict) -> Optional[str]:
    """
    Synchronous entry point — used by worker.py.
    Call this from Celery tasks and sync code paths.
    """
    if not settings.has_ai:
        return None

    prompt = _build_prompt(analysis)
    return _call_gemini_sync(prompt)


async def generate_explanation(analysis: dict) -> Optional[str]:
    """
    Async entry point — used when called directly from FastAPI route handlers.
    Runs the sync Gemini call in a thread executor so it does not block
    the event loop.
    """
    if not settings.has_ai:
        return None

    prompt = _build_prompt(analysis)

    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _call_gemini_sync(prompt))