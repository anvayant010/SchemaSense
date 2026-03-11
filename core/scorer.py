from __future__ import annotations
import json
from typing import Dict, Any, Tuple
import re

from core.models import ParsedSchema

DEFAULT_WEIGHTS = {
    "type_support": 0.60,
    "constraint_support": 0.25,
    "special_support": 0.15
}

CANONICAL_TYPE_MAP = {
    "INT": "INT", "INTEGER": "INT", "INT4": "INT", "MEDIUMINT": "INT", "SERIAL": "INT",
    "SMALLINT": "SMALLINT", "INT2": "SMALLINT", "TINYINT": "TINYINT",
    "BIGINT": "BIGINT", "INT8": "BIGINT", "BIGSERIAL": "BIGINT", "LONG": "BIGINT",
    
    "DECIMAL": "DECIMAL", "NUMERIC": "DECIMAL", "NUMBER": "DECIMAL", "MONEY": "MONEY",
    "FLOAT": "FLOAT", "REAL": "FLOAT", "DOUBLE": "DOUBLE", "DOUBLE PRECISION": "DOUBLE",
    "FLOAT8": "DOUBLE",
    
    "VARCHAR": "VARCHAR", "CHARACTER VARYING": "VARCHAR", "VARCHAR2": "VARCHAR",
    "NVARCHAR": "VARCHAR", "NVARCHAR2": "VARCHAR", "STRING": "VARCHAR",
    "CHAR": "CHAR", "CHARACTER": "CHAR", "BPCHAR": "CHAR",
    "TEXT": "TEXT", "CLOB": "CLOB", "LONGTEXT": "TEXT", "MEDIUMTEXT": "TEXT",
    
    "BLOB": "BLOB", "BYTEA": "BLOB", "VARBINARY": "BLOB", "BINARY": "BLOB",
    
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP", "DATETIME": "TIMESTAMP", "TIMESTAMPTZ": "TIMESTAMPTZ",
    "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ", "TIMETZ": "TIMETZ",
    
    "JSON": "JSON", "JSONB": "JSONB", "JSON[]": "JSON", "OBJECT": "JSON", "DOCUMENT": "JSON",
    "BOOLEAN": "BOOLEAN", "BOOL": "BOOLEAN", "BIT": "BOOLEAN",
    "UUID": "UUID",
    "GEOMETRY": "GEOMETRY", "POINT": "GEOMETRY", "POLYGON": "GEOMETRY",
    "ARRAY": "ARRAY",
}
TYPE_ALIASES = {
    "VARCHAR": {"VARCHAR", "VARCHAR2", "CHARACTER VARYING", "STRING", "TEXT"},
    "INT": {"INT", "INTEGER", "NUMBER", "SMALLINT", "BIGINT", "TINYINT"},
    "DECIMAL": {"DECIMAL", "NUMERIC", "NUMBER"},
    "TEXT": {"TEXT", "CLOB", "LONGTEXT", "MEDIUMTEXT"},
    "JSON": {"JSON", "JSONB", "DOCUMENT", "OBJECT"},
    "BLOB": {"BLOB", "BYTEA", "BINARY", "VARBINARY"},
}

def _parse_and_canonicalize_type(type_str: str | None) -> tuple[str, int | None, int | None, int | None]:
    """Parse type string → (canonical_type, length, precision, scale)"""
    if not type_str:
        return "TEXT", None, None, None
    
    s = str(type_str).strip().upper()
    
    match = re.match(r"^([A-Z0-9_]+)(?:\s*\(\s*(\d+)(?:\s*,\s*(\d+))?\s*\))?", s)
    if not match:
        return s, None, None, None
    
    base = match.group(1)
    length = int(match.group(2)) if match.group(2) else None
    precision = int(match.group(2)) if match.group(2) and match.group(3) else None
    scale = int(match.group(3)) if match.group(3) else None
    
    canon = CANONICAL_TYPE_MAP.get(base, base)
    return canon, length, precision, scale


def _load_db_profiles(path: str) -> Dict[str, Dict[str, Any]]:
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
            "varchar_max_length": None,    
            "decimal_max_precision": None,
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
    Returns sorted dict: {db_name: {raw_score, absolute_pct, relative_pct, explanation}}
    """
    if type_map is None:
        type_map = CANONICAL_TYPE_MAP
    if weights is None:
        weights = DEFAULT_WEIGHTS

    if not schema.tables or schema.total_columns == 0:
        return {}

    profiles = _load_db_profiles(db_features_path)

    total_columns = schema.total_columns
    constraint_counts = {
        "pk": schema.primary_keys_count,
        "fk": schema.foreign_keys_count,
        "unique": 0,
        "not_null": 0,
    }
    special_counts = {"json": 0, "geometry": 0, "blob": 0}

    for table in schema.tables:
        for col in table.columns:
            if col.is_unique or any("UNIQUE" in c.upper() for c in col.constraints):
                constraint_counts["unique"] += 1
            if not col.nullable:
                constraint_counts["not_null"] += 1

            canon, _, _, _ = _parse_and_canonicalize_type(col.raw_type or col.data_type)
            if canon in ("JSON", "JSONB"):
                special_counts["json"] += 1
            if canon in ("GEOMETRY", "POINT", "POLYGON"):
                special_counts["geometry"] += 1
            if canon in ("BLOB", "BYTEA", "CLOB"):
                special_counts["blob"] += 1

    results = {}
    raw_scores = {}

    for db_name, prof in profiles.items():
        supported_cols = 0
        type_violations = 0

        for table in schema.tables:
            for col in table.columns:
                input_type = col.raw_type if col.raw_type else col.data_type
                canon, length, precision, scale = _parse_and_canonicalize_type(input_type)

                def is_type_supported(canon: str, supported: set) -> bool:
                    if canon in supported:
                        return True
                    aliases = TYPE_ALIASES.get(canon, set())
                    return any(alias in supported for alias in aliases)

                is_supported = is_type_supported(canon, prof["supported_types"])

                if is_supported and length is not None:
                    max_len_key = f"{canon.lower()}_max_length"
                    max_len = prof.get(max_len_key)
                    if max_len is not None and length > max_len:
                        is_supported = False
                        type_violations += 1

                if is_supported and precision is not None:
                    max_prec_key = f"{canon.lower()}_max_precision"
                    max_prec = prof.get(max_prec_key)
                    if max_prec is not None and precision > max_prec:
                        is_supported = False
                        type_violations += 1

                if is_supported:
                    supported_cols += 1

        type_frac = supported_cols / total_columns if total_columns > 0 else 1.0

        if type_violations > 0:
            penalty = min(0.4, type_violations * 0.08)  
            type_frac *= (1 - penalty)
            type_frac = max(0.0, type_frac)

        constraint_total = sum(constraint_counts.values())
        constraint_frac = 1.0 if constraint_total == 0 else (
            constraint_counts["pk"] +
            (constraint_counts["fk"] if prof.get("supports_fk", False) else 0) +
            (constraint_counts["unique"] if prof.get("supports_unique", True) else 0) +
            constraint_counts["not_null"]
        ) / constraint_total

        special_total = sum(special_counts.values()) or 1
        special_supported = 0
        if special_counts["json"] > 0 and (
            "JSON" in prof["supported_types"] or "JSONB" in prof["supported_types"] or
            prof.get("supports_json_indexing", False)
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
            "type_violations": type_violations,
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