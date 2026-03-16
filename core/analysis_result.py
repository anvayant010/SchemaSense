from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ColumnMigrationNote(BaseModel):
    """A specific, actionable note about a single column for a target DB."""
    table: str
    column: str
    issue: str
    suggestion: str
    severity: str = Field(..., description="'error' | 'warning' | 'info'")


class DBScore(BaseModel):
    """Compatibility result for one target database."""
    db_name: str
    absolute_pct: float = Field(..., description="Score as % of max possible (0–100)")
    relative_pct: float = Field(..., description="Share of total score across all DBs (0–100)")
    type_support_frac: float
    constraint_frac: float
    special_frac: float
    type_violations: int
    migration_notes: List[ColumnMigrationNote] = Field(default_factory=list)
    migration_warnings: List[str] = Field(default_factory=list)
    overall_verdict: str = Field(..., description="'excellent' | 'good' | 'fair' | 'poor'")

    @property
    def verdict_label(self) -> str:
        mapping = {
            "excellent": "Excellent fit",
            "good": "Good fit",
            "fair": "Fair fit — changes needed",
            "poor": "Poor fit — significant rework required",
        }
        return mapping.get(self.overall_verdict, self.overall_verdict)


class ComplexityReport(BaseModel):
    table_count: int
    total_columns: int
    foreign_key_count: int
    join_density: float
    dependency_depth: int
    hub_tables: List[str] = Field(default_factory=list)
    fanout_tables: List[str] = Field(default_factory=list)
    complexity_score: float
    complexity_label: str = Field(..., description="'low' | 'medium' | 'high'")


class QualityReport(BaseModel):
    quality_score: float = Field(..., description="0–10")
    quality_label: str
    tables_without_pk: List[str] = Field(default_factory=list)
    fk_without_index: List[tuple] = Field(default_factory=list)
    weak_tables: List[str] = Field(default_factory=list)
    nullable_ratio: Dict[str, float] = Field(default_factory=dict)


class MigrationRiskReport(BaseModel):
    risk_score: float
    risk_level: str = Field(..., description="'LOW' | 'MEDIUM' | 'HIGH'")
    risk_factors: List[str] = Field(default_factory=list)


class MigrationPlan(BaseModel):
    table_creation_order: List[str] = Field(default_factory=list)
    constraint_steps: List[str] = Field(default_factory=list)
    index_steps: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """
    Top-level structured output from a full SchemaSense analysis.
    This is the single object returned by the engine — API, CLI, and UI all consume this.
    """
    source_file: Optional[str] = None
    source_format: str

    # Schema summary
    total_tables: int
    total_columns: int
    primary_keys_count: int
    foreign_keys_count: int
    type_distribution: Dict[str, int] = Field(default_factory=dict)
    has_advanced_types: bool

    complexity: ComplexityReport
    quality: QualityReport
    migration_risk: MigrationRiskReport
    migration_plan: MigrationPlan

    db_scores: List[DBScore] = Field(default_factory=list)

    @property
    def top_recommendation(self) -> Optional[DBScore]:
        return self.db_scores[0] if self.db_scores else None

    def to_cli_summary(self) -> str:
        """Human-readable summary for CLI output."""
        lines = []
        lines.append(f"Tables: {self.total_tables}  |  Columns: {self.total_columns}  |  FKs: {self.foreign_keys_count}")
        lines.append(f"Quality: {self.quality.quality_score}/10  |  Complexity: {self.complexity.complexity_label}  |  Migration risk: {self.migration_risk.risk_level}")
        if self.top_recommendation:
            lines.append(f"Top match: {self.top_recommendation.db_name} ({self.top_recommendation.absolute_pct:.1f}%)")
        return "\n".join(lines)

    class Config:
        extra = "forbid"