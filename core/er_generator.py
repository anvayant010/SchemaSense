from __future__ import annotations
from core.models import ParsedSchema


def generate_mermaid_er(schema: ParsedSchema) -> str:
    """
    Generate a Mermaid erDiagram string from a ParsedSchema.
    Output can be pasted directly into mermaid.live, Notion, GitHub README, etc.
    """
    if not schema.tables:
        return "erDiagram\n  %% No tables found"

    lines = ["erDiagram"]

    # Entity definitions
    for table in schema.tables:
        lines.append(f"  {table.name} {{")
        for col in table.columns:
            type_str = col.data_type
            if col.length:
                type_str += f"({col.length})"
            elif col.precision and col.scale:
                type_str += f"({col.precision},{col.scale})"

            key = ""
            if col.is_primary_key:
                key = " PK"
            elif col.is_foreign_key:
                key = " FK"
            elif col.is_unique:
                key = " UK"

            col_name = col.name.replace(" ", "_")
            lines.append(f"    {type_str} {col_name}{key}")
        lines.append("  }")

    lines.append("")

    # Relationships from FK columns
    relationships = []
    for table in schema.tables:
        for col in table.columns:
            if col.is_foreign_key and col.references:
                ref_table = col.references.get("table")
                ref_col   = col.references.get("column", "id")
                if ref_table:
                    rel = f'  {table.name} }}o--|| {ref_table} : "{col.name}"'
                    relationships.append(rel)

    lines.extend(relationships)

    return "\n".join(lines)


def get_er_summary(schema: ParsedSchema) -> dict:
    """Return metadata about the ER diagram for the API response."""
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