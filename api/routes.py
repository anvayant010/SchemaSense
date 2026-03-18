from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from api.config import settings

router = APIRouter()

ALLOWED_FORMATS = {"csv", "sql", "json"}
ALLOWED_EXTENSIONS = {".csv", ".sql", ".json"}


def _validate_upload(file: UploadFile, input_format: str) -> None:
    if input_format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported format '{input_format}'. Must be one of: {', '.join(ALLOWED_FORMATS)}"
        )
    suffix = Path(file.filename or "").suffix.lower()
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"File extension '{suffix}' not allowed."
        )


async def _save_upload(file: UploadFile, suffix: str) -> str:
    """Save upload to a temp file, return its path."""
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_bytes // 1024 // 1024}MB."
        )
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        dir=tempfile.gettempdir(),
    )
    tmp.write(content)
    tmp.close()
    return tmp.name


# ── Health check 

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "ai_enabled": settings.has_ai,
        "async_mode": settings.use_celery,
    }


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(..., description="Schema file to analyze"),
    format: str = Form(..., description="Input format: csv | sql | json"),
    dialect: Optional[str] = Form(None, description="SQL dialect hint: postgres | mysql | sqlite etc."),
    async_mode: Optional[bool] = Form(None, description="Force async (true) or sync (false). Defaults to auto."),
):
    """
    Upload a schema file and analyze it.

    - **Sync mode** (default when Redis unavailable): returns the full result immediately.
    - **Async mode** (when Redis is available): returns a job_id, poll /results/{job_id}.
    """
    _validate_upload(file, format)
    suffix = f".{format}"
    file_path = await _save_upload(file, suffix)

    use_async = async_mode if async_mode is not None else settings.use_celery

    if use_async:
        try:
            from api.worker import analyze_task
            task = analyze_task.delay(file_path, format, dialect)
            return JSONResponse(
                status_code=202,
                content={
                    "job_id": task.id,
                    "status": "queued",
                    "poll_url": f"/results/{task.id}",
                }
            )
        except Exception as e:
            pass

    # Synchronous path
    try:
        from api.worker import run_analysis_sync
        result = run_analysis_sync(file_path, format, dialect)
        return JSONResponse(status_code=200, content=result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Parsing failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {type(e).__name__}: {e}")



@router.get("/results/{job_id}")
async def get_result(job_id: str):
    """
    Poll for the result of an async analysis job.

    Returns:
    - 200 + result when complete
    - 202 + status when still running
    - 500 if the job failed
    """
    try:
        from celery.result import AsyncResult
        from api.worker import celery_app

        task = AsyncResult(job_id, app=celery_app)

        if task.state == "PENDING":
            return JSONResponse(status_code=202, content={"status": "pending", "job_id": job_id})

        elif task.state == "PROGRESS":
            meta = task.info or {}
            return JSONResponse(status_code=202, content={
                "status": "processing",
                "step": meta.get("step", "analyzing"),
                "job_id": job_id,
            })

        elif task.state == "SUCCESS":
            return JSONResponse(status_code=200, content=task.result)

        elif task.state == "FAILURE":
            return JSONResponse(status_code=500, content={
                "status": "error",
                "error": str(task.result),
                "job_id": job_id,
            })

        else:
            return JSONResponse(status_code=202, content={"status": task.state, "job_id": job_id})

    except ImportError:
        raise HTTPException(status_code=503, detail="Async mode not available — Redis not configured.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Supported databases info 

@router.get("/databases")
async def list_databases():
    """Return the list of databases SchemaSense can score against."""
    import json
    try:
        with open(settings.db_features_path) as f:
            data = json.load(f)
        return {
            "count": len(data),
            "databases": [
                {"name": name, "notes": info.get("notes", "")}
                for name, info in data.items()
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))