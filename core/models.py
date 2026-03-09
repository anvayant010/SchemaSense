from __future__ import annotations

from typing import List, Optional, Literal, Dict, Any, Set
from pydantic import BaseModel, Field, computed_field, model_validator
from collections import Counter


class Column(BaseModel):
    """
    Represents a single column in a table.
    All fields are normalized / cleaned by the parser.
    """
    name: str = Field(..., description="Column name (normalized: lowercase, no quotes)")
    data_type: str = Field(..., description="Normalized data type e.g. 'INT', 'VARCHAR', 'JSONB', 'TEXT'")
    raw_type: Optional[str] = Field(None, description="Original type string from input")
    length: Optional[int] = Field(None, description="Length for string types e.g. 255")
    precision: Optional[int] = None
    scale: Optional[int] = None

    nullable: bool = Field(True, description="Can this column contain NULL?")
    default: Optional[Any] = Field(None, description="Default value expression if any")

    is_primary_key: bool = Field(False)
    is_foreign_key: bool = Field(False)
    is_unique: bool = Field(False)

    references: Optional[Dict[str, str]] = Field(
        None,
        description="For foreign keys: {'table': 'departments', 'column': 'id'}"
    )

    constraints: List[str] = Field(
        default_factory=list,
        description="Raw constraint strings e.g. ['NOT NULL', 'CHECK (age > 0)']"
    )

    @computed_field
    @property
    def constraint_summary(self) -> str:
        parts = []
        if self.is_primary_key:
            parts.append("PK")
        if self.is_foreign_key:
            parts.append(f"FK→{self.references.get('table','?')}.{self.references.get('column','?')}" if self.references else "FK")
        if self.is_unique:
            parts.append("UNIQUE")
        if not self.nullable:
            parts.append("NOT NULL")
        if self.default is not None:
            parts.append(f"DEFAULT {self.default}")
        return " | ".join(parts) or "—"

    class Config:
        extra = "forbid"  


class Table(BaseModel):
    """
    Represents a database table (or collection in document DBs)
    """
    name: str = Field(..., description="Table name (normalized)")
    columns: List[Column] = Field(default_factory=list)

    @computed_field
    @property
    def column_count(self) -> int:
        return len(self.columns)

    @computed_field
    @property
    def pk_columns(self) -> List[str]:
        return [c.name for c in self.columns if c.is_primary_key]

    @computed_field
    @property
    def fk_columns(self) -> List[str]:
        return [c.name for c in self.columns if c.is_foreign_key]

    def get_column(self, name: str) -> Optional[Column]:
        for col in self.columns:
            if col.name == name:
                return col
        return None

    class Config:
        extra = "forbid"


class ParsedSchema(BaseModel):
    """
    Top-level container for the parsed & normalized schema.
    This is what parser returns and analyzer/scorer consume.
    """
    tables: List[Table] = Field(default_factory=list)
    source_format: Literal["csv", "sql", "json", "unknown"] = "unknown"
    source_file: Optional[str] = None

    # Computed summary fields
    @computed_field
    @property
    def total_tables(self) -> int:
        return len(self.tables)

    @computed_field
    @property
    def total_columns(self) -> int:
        return sum(t.column_count for t in self.tables)

    @computed_field
    @property
    def primary_keys_count(self) -> int:
        return sum(len(t.pk_columns) for t in self.tables)

    @computed_field
    @property
    def foreign_keys_count(self) -> int:
        return sum(len(t.fk_columns) for t in self.tables)

    @computed_field
    @property
    def type_distribution(self) -> Dict[str, int]:
        counter = Counter()
        for table in self.tables:
            for col in table.columns:
                counter[col.data_type] += 1
        return dict(counter.most_common())

    @computed_field
    @property
    def has_advanced_types(self) -> bool:
        advanced = {"JSON", "JSONB", "ARRAY", "UUID", "GEOMETRY", "INET", "XML"}
        return any(t in self.type_distribution for t in advanced)

    # Small validation
    @model_validator(mode="after")
    def check_unique_column_names_per_table(self):
        for table in self.tables:
            names = [c.name for c in table.columns]
            if len(names) != len(set(names)):
                raise ValueError(f"Duplicate column names found in table '{table.name}'")
        return self

    def to_summary_dict(self) -> dict:
        """Simple dict for console printing or logging"""
        return {
            "tables": self.total_tables,
            "columns": self.total_columns,
            "pks": self.primary_keys_count,
            "fks": self.foreign_keys_count,
            "types": self.type_distribution,
            "advanced_types": self.has_advanced_types,
        }

    class Config:
        extra = "forbid"