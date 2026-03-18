from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from celery import Celery
from api.config import settings

celery_app = Celery(
    "schemasense",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=settings.result_ttl,
    task_track_started=True,
    worker_prefetch_multiplier=1,  
)


def _run_analysis(file_path: str, input_format: str, dialect: str | None) -> Dict[str, Any]:
    """
    Core analysis pipeline — runs the full Phase 0 engine and returns
    a serializable dict. Imported here to avoid circular imports.
    """
    from parser.schema_parser import SchemaParser
    from core.scorer import score_schema
    from core.schema_graph import SchemaGraph
    from core.schema_complexity import SchemaComplexityAnalyzer
    from core.schema_quality import SchemaQualityAnalyzer
    from core.migration_risk import MigrationRiskAnalyzer
    from core.migration_planner import MigrationPlanner

    schema_parser = SchemaParser(
        input_file=file_path,
        input_format=input_format,
        dialect=dialect,
    )
    schema = schema_parser.parse()

    graph = SchemaGraph(schema)
    graph.build_graph()
    complexity = SchemaComplexityAnalyzer(schema)
    quality = SchemaQualityAnalyzer(schema)
    risk = MigrationRiskAnalyzer(schema)
    planner = MigrationPlanner(schema)

    complexity_label = (
        "low" if complexity.complexity_score() < 5
        else "medium" if complexity.complexity_score() < 15
        else "high"
    )

    quality_score = quality.quality_score()
    quality_label = (
        "excellent" if quality_score >= 9
        else "good" if quality_score >= 7
        else "fair" if quality_score >= 5
        else "poor"
    )

    scoring_results = score_schema(
        schema,
        db_features_path=settings.db_features_path,
    )

    plan = planner.generate_plan()

    return {
        "schema_summary": schema.to_summary_dict(),
        "source_format": schema.source_format,
        "source_file": Path(file_path).name,
        "complexity": {
            "table_count": complexity.table_count(),
            "foreign_key_count": complexity.foreign_key_count(),
            "join_density": round(complexity.join_density(), 3),
            "dependency_depth": complexity.dependency_depth(),
            "hub_tables": complexity.hub_tables(),
            "fanout_tables": complexity.fanout_tables(),
            "complexity_score": complexity.complexity_score(),
            "complexity_label": complexity_label,
        },
        "quality": {
            "quality_score": quality_score,
            "quality_label": quality_label,
            "tables_without_pk": quality.tables_without_primary_keys(),
            "fk_without_index": quality.fk_without_index(),
            "weak_tables": quality.weak_tables(),
        },
        "migration_risk": {
            "risk_score": risk.risk_score(),
            "risk_level": risk.risk_level(),
            "risk_factors": risk.risk_factors(),
        },
        "migration_plan": {
            "table_creation_order": plan["table_creation_order"],
            "constraint_steps": plan["constraint_plan"],
            "index_steps": plan["index_plan"],
        },
        "db_scores": scoring_results,
        "graph": {
            "dependency_depth": graph.dependency_depth(),
            "join_density": round(graph.join_density(), 3),
            "cycles": graph.detect_cycles(),
            "migration_order": graph.migration_order(),
        },
    }


@celery_app.task(bind=True, name="schemasense.analyze")
def analyze_task(self, file_path: str, input_format: str, dialect: str | None = None) -> Dict[str, Any]:
    """
    Celery task — runs analysis and AI explanation, stores result.
    The task result is stored automatically in Redis by Celery.
    """
    try:
        self.update_state(state="PROGRESS", meta={"step": "parsing"})
        result = _run_analysis(file_path, input_format, dialect)

        self.update_state(state="PROGRESS", meta={"step": "explaining"})
        try:
            from api.ai_explainer import generate_explanation_sync
            result["ai_explanation"] = generate_explanation_sync(result)
        except Exception:
            result["ai_explanation"] = None

        try:
            os.unlink(file_path)
        except Exception:
            pass

        return {"status": "success", "result": result}

    except Exception as exc:
        try:
            os.unlink(file_path)
        except Exception:
            pass
        return {
            "status": "error",
            "error": str(exc),
            "detail": traceback.format_exc(),
        }


def run_analysis_sync(file_path: str, input_format: str, dialect: str | None = None) -> Dict[str, Any]:
    """
    Synchronous fallback — used when Redis/Celery is not available.
    Returns the result directly instead of via a job ID.
    """
    result = _run_analysis(file_path, input_format, dialect)

    try:
        from api.ai_explainer import generate_explanation_sync
        result["ai_explanation"] = generate_explanation_sync(result)
    except Exception:
        result["ai_explanation"] = None

    try:
        os.unlink(file_path)
    except Exception:
        pass

    return {"status": "success", "result": result}