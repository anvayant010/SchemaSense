from __future__ import annotations
import json
import re
from typing import Dict, Any, Tuple

from core.models import ParsedSchema, Column

DEFAULT_WEIGHTS = {
    "type_support": 0.60,
    "constraint_support": 0.25,
    "special_support": 0.15
}

_type_regex = re.compile(r"^([a-zA-Z0-9_]+)\s*(?:\(\s*([0-9]+)\s*(?:,\s*([0-9]+)\s*)?\))?$")

CANONICAL_TYPE_MAP = {
    "INT": "INT", "INTEGER": "INT", "SMALLINT": "SMALLINT", "BIGINT": "BIGINT",
    "NUMBER": "DECIMAL", "NUMERIC": "DECIMAL", "DECIMAL": "DECIMAL",
    "FLOAT": "FLOAT", "DOUBLE": "DOUBLE", "REAL": "FLOAT",
    "VARCHAR": "VARCHAR", "VARCHAR2": "VARCHAR", "NVARCHAR": "VARCHAR", "NVARCHAR2": "VARCHAR",
    "CHAR": "CHAR", "CHARACTER": "CHAR", "TEXT": "TEXT", "CLOB": "CLOB",
    "BLOB": "BLOB", "BYTEA": "BLOB",
    "DATE": "DATE", "TIMESTAMP": "TIMESTAMP", "DATETIME": "TIMESTAMP", "TIME": "TIME",
    "JSON": "JSON", "JSONB": "JSON", "JSON[]": "JSON",
    "BOOLEAN": "BOOLEAN", "BOOL": "BOOLEAN",
    "UUID": "UUID",
    "GEOMETRY": "GEOMETRY", "POINT": "GEOMETRY", "POLYGON": "GEOMETRY",
    "ARRAY": "ARRAY",
}

def _parse_type(type_str: str | None) -> Tuple[str, int]:
    """Parse type string → (base_type_upper, length_or_precision_or_0)"""
    if not type_str:
        return "TEXT", 0
    s = str(type_str).strip().upper()
    m = _type_regex.match(s)
    if not m:
        return s, 0
    base = m.group(1)
    length_str = m.group(2)
    length = int(length_str) if length_str else 0
    return base, length


def _canonicalize_type(base_type: str) -> str:
    """Map to canonical type name"""
    b = base_type.upper()
    return CANONICAL_TYPE_MAP.get(b, b)


def _load_db_profiles(path: str) -> Dict[str, Dict[str, Any]]:
    """Load and normalize database capability profiles"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    profiles = {}
    for db_name, prof in data.items():
        p = dict(prof)
        supp = prof.get("supported_types", [])
        p["supported_types"] = {str(x).strip().upper() for x in supp}
        defaults = {
            "supports_fk": False,
            "supports_unique": True,
            "supports_check": False,
            "supports_json_indexing": False,
            "supports_partitioning": False,
            "supports_stored_procs": False,
        }
        for k, default in defaults.items():
            p.setdefault(k, default)
        profiles[db_name] = p
    return profiles


def score_schema(
    schema: ParsedSchema,
    db_features_path: str = "data/db_features.json",
    type_map: Dict[str, str] | None = None,
    weights: Dict[str, float] | None = None
) -> Dict[str, Any]:
    """
    Score the schema against all known databases.
    Returns sorted dict of {db_name: {absolute_pct, relative_pct, explanation, raw_score}}
    """
    if type_map is None:
        type_map = CANONICAL_TYPE_MAP
    if weights is None:
        weights = DEFAULT_WEIGHTS

    if not schema.tables or schema.total_columns == 0:
        return {}

    profiles = _load_db_profiles(db_features_path)

    type_counts: Dict[str, int] = schema.type_distribution 
    total_columns = schema.total_columns

    constraint_counts = {
        "pk": schema.primary_keys_count,
        "fk": schema.foreign_keys_count,
        "unique": 0,         
        "not_null": 0,
    }
    special_counts = {
        "json": 0,
        "geometry": 0,
        "blob": 0,
    }

    for table in schema.tables:
        for col in table.columns:
            if col.is_unique or "UNIQUE" in [c.upper() for c in col.constraints]:
                constraint_counts["unique"] += 1

            if not col.nullable:
                constraint_counts["not_null"] += 1

            canon = _canonicalize_type(col.data_type)
            if canon in ("JSON", "JSONB"):
                special_counts["json"] += 1
            if canon in ("GEOMETRY", "POINT", "POLYGON"):
                special_counts["geometry"] += 1
            if canon in ("BLOB", "BYTEA", "CLOB"):
                special_counts["blob"] += 1

    results: Dict[str, Any] = {}
    raw_scores: Dict[str, float] = {}

    for db_name, prof in profiles.items():
        # Type support
        supported_cols = sum(
            cnt for tname, cnt in type_counts.items()
            if _canonicalize_type(tname) in prof["supported_types"]
        )
        type_frac = supported_cols / total_columns if total_columns > 0 else 1.0

        # Constraint support
        constraint_total = sum(constraint_counts.values())
        if constraint_total == 0:
            constraint_frac = 1.0
        else:
            supported_constraints = (
                constraint_counts["pk"] +          
                (constraint_counts["fk"] if prof.get("supports_fk") else 0) +
                (constraint_counts["unique"] if prof.get("supports_unique") else 0) +
                constraint_counts["not_null"]     
            )
            constraint_frac = supported_constraints / constraint_total

        # Special features
        special_total = sum(special_counts.values()) or 1
        special_supported = 0
        if special_counts["json"] > 0 and (
            "JSON" in prof["supported_types"] or "JSONB" in prof["supported_types"] or
            prof.get("supports_json_indexing")
        ):
            special_supported += special_counts["json"]
        if special_counts["geometry"] > 0 and "GEOMETRY" in prof["supported_types"]:
            special_supported += special_counts["geometry"]
        if special_counts["blob"] > 0 and any(t in prof["supported_types"] for t in ("BLOB", "BYTEA")):
            special_supported += special_counts["blob"]
        special_frac = special_supported / special_total

        raw = (
            weights["type_support"] * type_frac +
            weights["constraint_support"] * constraint_frac +
            weights["special_support"] * special_frac
        )

        explanation = {
            "type_support_frac": round(type_frac, 4),
            "constraint_frac": round(constraint_frac, 4),
            "special_frac": round(special_frac, 4),
            "weights": weights
        }

        raw_scores[db_name] = raw
        results[db_name] = {
            "raw_score": round(raw, 4),
            "absolute_pct": round(raw * 100, 2),
            "explanation": explanation
        }

    total_raw = sum(raw_scores.values()) or 1.0
    for db_name in results:
        rel = (raw_scores[db_name] / total_raw) * 100
        results[db_name]["relative_pct"] = round(rel, 2)

    sorted_results = dict(
        sorted(results.items(), key=lambda item: item[1]["raw_score"], reverse=True)
    )

    return sorted_results