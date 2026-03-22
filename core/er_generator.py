from __future__ import annotations
import re
from core.models import ParsedSchema


def _safe_type(data_type: str, length=None, precision=None, scale=None) -> str:
    """
    Produce a Mermaid v11-safe type string.
    Mermaid erDiagram does NOT allow parentheses in type names.
    VARCHAR(255) → VARCHAR255, DECIMAL(10,2) → DECIMAL10_2
    """
    base = re.sub(r'[^A-Za-z0-9_]', '', data_type)  # strip all non-alphanumeric
    if not base:
        base = "TEXT"

    if length:
        base = f"{base}{length}"
    elif precision and scale:
        base = f"{base}{precision}_{scale}"
    elif precision:
        base = f"{base}{precision}"

    return base


def _safe_name(name: str) -> str:
    """
    Sanitize identifiers for Mermaid v11.
    Only alphanumeric and underscores allowed.
    """
    return re.sub(r'[^A-Za-z0-9_]', '_', name).strip('_') or 'unknown'


def generate_mermaid_er(schema: ParsedSchema) -> str:
    """
    Generate a Mermaid v11-compatible erDiagram string.
    
    Key rules for Mermaid v11 erDiagram:
    - Type names: alphanumeric + underscore only, NO parentheses
    - Attribute names: alphanumeric + underscore only
    - Relationship labels: must be quoted strings
    - Entity names: alphanumeric + underscore only
    """
    if not schema.tables:
        return "erDiagram\n  %% No tables found"

    lines = ["erDiagram"]
    lines.append("")

    # Entity definitions
    for table in schema.tables:
        entity_name = _safe_name(table.name)
        lines.append(f"  {entity_name} {{")

        for col in table.columns:
            type_str = _safe_type(col.data_type, col.length, col.precision, col.scale)
            col_name = _safe_name(col.name)

            # Key annotation — PK, FK, UK
            if col.is_primary_key:
                key = " PK"
            elif col.is_foreign_key:
                key = " FK"
            elif col.is_unique:
                key = " UK"
            else:
                key = ""

            lines.append(f"    {type_str} {col_name}{key}")

        lines.append("  }")
        lines.append("")

    # Relationships
    seen = set()
    for table in schema.tables:
        for col in table.columns:
            if col.is_foreign_key and col.references:
                ref_table = col.references.get("table")
                if not ref_table:
                    continue

                from_entity = _safe_name(table.name)
                to_entity   = _safe_name(ref_table)
                label       = _safe_name(col.name)

                # Deduplicate relationships
                key = (from_entity, to_entity, label)
                if key in seen:
                    continue
                seen.add(key)

                # }o--|| = many-to-one (FK side is many, referenced is one)
                lines.append(f'  {from_entity} }}o--|| {to_entity} : "{label}"')

    return "\n".join(lines)


def get_er_summary(schema: ParsedSchema) -> dict:
    """Return ER diagram data for the API response."""
    fk_pairs = []
    for table in schema.tables:
        for col in table.columns:
            if col.is_foreign_key and col.references:
                fk_pairs.append({
                    "from_table":  table.name,
                    "from_column": col.name,
                    "to_table":    col.references.get("table"),
                    "to_column":   col.references.get("column"),
                })

    return {
        "mermaid_code": generate_mermaid_er(schema),
        "table_count":  schema.total_tables,
        "relationship_count": len(fk_pairs),
        "relationships": fk_pairs,
    }