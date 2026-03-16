from __future__ import annotations
import json
from typing import Dict, Any, List
import re

from core.models import ParsedSchema
from core.analysis_result import DBScore, ColumnMigrationNote

DEFAULT_WEIGHTS = {
    "type_support": 0.60,
    "constraint_support": 0.25,
    "special_support": 0.15
}

CANONICAL_TYPE_MAP = {
    "INT": "INT", "INTEGER": "INT", "INT4": "INT", "MEDIUMINT": "INT", "SERIAL": "INT",
    "SMALLINT": "SMALLINT", "INT2": "SMALLINT", "TINYINT": "TINYINT",
    "BIGINT": "BIGINT", "INT8": "BIGINT", "BIGSERIAL": "BIGINT", "LONG": "BIGINT",
    "INT64": "BIGINT", "INT32": "INT",
    "DECIMAL": "DECIMAL", "NUMERIC": "DECIMAL", "NUMBER": "DECIMAL", "BIGNUMERIC": "DECIMAL",
    "MONEY": "MONEY", "SMALLMONEY": "MONEY",
    "FLOAT": "FLOAT", "REAL": "FLOAT", "FLOAT4": "FLOAT", "BINARY_FLOAT": "FLOAT",
    "DOUBLE": "DOUBLE", "DOUBLE PRECISION": "DOUBLE", "FLOAT8": "DOUBLE", "FLOAT64": "DOUBLE",
    "BINARY_DOUBLE": "DOUBLE",
    "VARCHAR": "VARCHAR", "CHARACTER VARYING": "VARCHAR", "VARCHAR2": "VARCHAR",
    "NVARCHAR": "VARCHAR", "NVARCHAR2": "VARCHAR", "STRING": "VARCHAR",
    "CHAR": "CHAR", "CHARACTER": "CHAR", "BPCHAR": "CHAR", "NCHAR": "CHAR",
    "TEXT": "TEXT", "CLOB": "CLOB", "LONGTEXT": "TEXT", "MEDIUMTEXT": "TEXT",
    "NTEXT": "TEXT", "NCLOB": "CLOB",
    "BLOB": "BLOB", "BYTEA": "BLOB", "VARBINARY": "BLOB", "BINARY": "BLOB",
    "BYTES": "BLOB", "IMAGE": "BLOB", "RAW": "BLOB",
    "MEDIUMBLOB": "BLOB", "LONGBLOB": "BLOB",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP", "DATETIME": "TIMESTAMP", "DATETIME2": "TIMESTAMP",
    "SMALLDATETIME": "TIMESTAMP",
    "TIMESTAMPTZ": "TIMESTAMPTZ", "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
    "DATETIMEOFFSET": "TIMESTAMPTZ",
    "TIMETZ": "TIMETZ",
    "JSON": "JSON", "JSONB": "JSONB", "JSON[]": "JSON", "OBJECT": "JSON",
    "DOCUMENT": "JSON",
    "BOOLEAN": "BOOLEAN", "BOOL": "BOOLEAN", "BIT": "BOOLEAN",
    "UUID": "UUID", "UNIQUEIDENTIFIER": "UUID",
    "GEOMETRY": "GEOMETRY", "POINT": "GEOMETRY", "POLYGON": "GEOMETRY",
    "ARRAY": "ARRAY",
    "INET": "INET",
    "XML": "XML", "XMLTYPE": "XML",
}

TYPE_ALIASES: Dict[str, set] = {
    "VARCHAR": {"VARCHAR", "VARCHAR2", "CHARACTER VARYING", "STRING", "TEXT", "NVARCHAR"},
    "INT": {"INT", "INTEGER", "NUMBER", "SMALLINT", "BIGINT", "TINYINT", "INT4", "INT8"},
    "DECIMAL": {"DECIMAL", "NUMERIC", "NUMBER", "BIGNUMERIC"},
    "TEXT": {"TEXT", "CLOB", "LONGTEXT", "MEDIUMTEXT", "NTEXT"},
    "CLOB": {"CLOB", "TEXT", "LONGTEXT", "NCLOB"},
    "JSON": {"JSON", "JSONB", "DOCUMENT", "OBJECT"},
    "JSONB": {"JSONB", "JSON"},
    "BLOB": {"BLOB", "BYTEA", "BINARY", "VARBINARY", "BYTES", "IMAGE", "RAW"},
    "BOOLEAN": {"BOOLEAN", "BOOL", "BIT"},
    "TIMESTAMP": {"TIMESTAMP", "DATETIME", "DATETIME2", "SMALLDATETIME"},
    "TIMESTAMPTZ": {"TIMESTAMPTZ", "TIMESTAMP WITH TIME ZONE", "DATETIMEOFFSET"},
    "UUID": {"UUID", "UNIQUEIDENTIFIER"},
    "DOUBLE": {"DOUBLE", "DOUBLE PRECISION", "FLOAT8", "FLOAT64", "BINARY_DOUBLE"},
    "FLOAT": {"FLOAT", "REAL", "FLOAT4", "BINARY_FLOAT"},
    "BIGINT": {"BIGINT", "INT8", "INT64"},
}

ADVANCED_TYPES = {"JSON", "JSONB", "ARRAY", "UUID", "GEOMETRY", "INET", "XML"}

RESERVED_WORDS: Dict[str, set] = {
    "MySQL": {"select", "where", "order", "group", "key", "read", "write", "match",
              "explain", "status", "data", "value", "values", "default", "index"},
    "SQL Server": {"select", "where", "key", "user", "data", "value", "table",
                   "identity", "timestamp", "index", "file", "read"},
    "Oracle": {"select", "where", "level", "comment", "size", "number", "date",
               "value", "user", "session", "type", "audit", "access"},
    "BigQuery": {"select", "where", "array", "struct", "date", "time", "timestamp",
                 "interval", "range", "any", "all"},
}


def _parse_and_canonicalize_type(type_str: str | None) -> tuple[str, int | None, int | None, int | None]:
    if not type_str:
        return "TEXT", None, None, None
    s = str(type_str).strip().upper()
    match = re.match(r"^([A-Z0-9_ ]+?)(?:\s*\(\s*(\d+)(?:\s*,\s*(\d+))?\s*\))?$", s.strip())
    if not match:
        base = re.split(r"[\s(]", s)[0]
        canon = CANONICAL_TYPE_MAP.get(base, base)
        return canon, None, None, None
    base = match.group(1).strip()
    p1 = int(match.group(2)) if match.group(2) else None
    p2 = int(match.group(3)) if match.group(3) else None
    canon = CANONICAL_TYPE_MAP.get(base, base)
    if canon in ("VARCHAR", "CHAR", "NVARCHAR"):
        return canon, p1, None, None
    elif canon == "DECIMAL" and p1 is not None:
        return canon, None, p1, p2
    else:
        return canon, p1, p2, None


def _load_db_profiles(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    profiles = {}
    for db_name, prof in data.items():
        p = dict(prof)
        supp = prof.get("supported_types", [])
        p["supported_types"] = {str(x).strip().upper() for x in supp}
        defaults = {
            "supports_fk": False, "supports_unique": True, "supports_check": False,
            "supports_not_null": True, "supports_default": True,
            "supports_json_indexing": False, "supports_array_type": False,
            "supports_partitioning": False, "supports_stored_procs": False,
            "supports_transactions": True, "supports_window_functions": False,
            "supports_cte": False, "varchar_max_length": None,
            "decimal_max_precision": None, "fk_disabled_by_default": False,
            "constraints_enforced": True,
        }
        for k, default in defaults.items():
            p.setdefault(k, default)
        profiles[db_name] = p
    return profiles


def _is_type_supported(canon: str, supported: set) -> bool:
    if canon in supported:
        return True
    aliases = TYPE_ALIASES.get(canon, set())
    return any(alias in supported for alias in aliases)


def _suggest_type_alternative(canon: str, db_name: str) -> str:
    suggestions = {
        ("UUID", "MySQL"): "Use CHAR(36) or BINARY(16) for UUID storage",
        ("UUID", "Oracle"): "Use RAW(16) with SYS_GUID() or VARCHAR2(36)",
        ("GEOMETRY", "SQLite"): "Use TEXT to store WKT (Well-Known Text) representations",
        ("GEOMETRY", "MongoDB"): "Use GeoJSON in a JSON field with a 2dsphere index",
        ("JSONB", "MySQL"): "Use the JSON type (MySQL 8.0+ binary JSON)",
        ("JSONB", "SQLite"): "Use TEXT column; SQLite has JSON functions but no dedicated type",
        ("ARRAY", "MySQL"): "Normalize into a child table with a FK reference",
        ("ARRAY", "Oracle"): "Use a nested table type or normalize into a child table",
        ("ARRAY", "SQL Server"): "Normalize into a child table with a FK reference",
        ("INET", "MySQL"): "Use VARCHAR(45) for IPv6 or INT UNSIGNED for IPv4",
        ("INET", "SQLite"): "Use TEXT column for IP address storage",
        ("XML", "MySQL"): "Use TEXT or LONGTEXT for XML data",
        ("XML", "SQLite"): "Use TEXT column for XML data",
        ("MONEY", "SQLite"): "Use DECIMAL(19,4) or INTEGER (store cents)",
        ("MONEY", "MongoDB"): "Use NumberDecimal type to avoid floating-point issues",
        ("TIMESTAMPTZ", "MySQL"): "Use DATETIME; MySQL handles UTC conversion but no explicit TZ storage",
        ("TIMESTAMPTZ", "SQLite"): "Use TEXT (ISO 8601) or INTEGER (Unix epoch)",
    }
    key = (canon, db_name)
    if key in suggestions:
        return suggestions[key]
    if canon in ("JSON", "JSONB"):
        return f"Store as VARCHAR/TEXT in {db_name} and parse at the application layer"
    if canon == "UUID":
        return f"Use VARCHAR(36) or DB-specific equivalent in {db_name}"
    if canon == "BOOLEAN":
        return "Use TINYINT(1) or NUMBER(1) as a boolean substitute"
    if canon in ("BLOB", "BYTEA"):
        return f"Use VARBINARY or LONGBLOB equivalent in {db_name}"
    return f"Check {db_name} documentation for the equivalent of {canon}"


def _generate_column_notes(schema: ParsedSchema, prof: dict, db_name: str) -> List[ColumnMigrationNote]:
    notes = []
    reserved = {w.lower() for w in RESERVED_WORDS.get(db_name, set())}

    for table in schema.tables:
        for col in table.columns:
            canon, length, precision, scale = _parse_and_canonicalize_type(col.raw_type or col.data_type)

            if col.name.lower() in reserved:
                notes.append(ColumnMigrationNote(
                    table=table.name, column=col.name,
                    issue=f"'{col.name}' is a reserved word in {db_name}",
                    suggestion=f"Rename to '{col.name}_value' or wrap in quotes in all queries",
                    severity="warning"
                ))

            if not _is_type_supported(canon, prof["supported_types"]):
                notes.append(ColumnMigrationNote(
                    table=table.name, column=col.name,
                    issue=f"Type '{col.data_type}' not natively supported in {db_name}",
                    suggestion=_suggest_type_alternative(canon, db_name),
                    severity="error"
                ))
                continue

            if canon in ("VARCHAR", "CHAR") and length is not None:
                max_len = prof.get("varchar_max_length")
                if max_len and length > max_len:
                    notes.append(ColumnMigrationNote(
                        table=table.name, column=col.name,
                        issue=f"VARCHAR({length}) exceeds {db_name} max of {max_len}",
                        suggestion=f"Change to TEXT/CLOB or reduce length to {max_len}",
                        severity="error"
                    ))

            if canon == "DECIMAL" and precision is not None:
                max_prec = prof.get("decimal_max_precision")
                if max_prec and precision > max_prec:
                    notes.append(ColumnMigrationNote(
                        table=table.name, column=col.name,
                        issue=f"DECIMAL({precision}) exceeds {db_name} max precision of {max_prec}",
                        suggestion=f"Reduce precision to {max_prec} or use FLOAT/DOUBLE",
                        severity="error"
                    ))

            if canon == "BOOLEAN" and db_name == "Oracle":
                notes.append(ColumnMigrationNote(
                    table=table.name, column=col.name,
                    issue="Oracle has no native BOOLEAN column type (pre-23c)",
                    suggestion="Use NUMBER(1) CHECK (col IN (0,1)) or CHAR(1) CHECK (col IN ('Y','N'))",
                    severity="warning"
                ))

            if canon in ("JSON", "JSONB") and db_name in ("SQL Server", "Redshift"):
                notes.append(ColumnMigrationNote(
                    table=table.name, column=col.name,
                    issue=f"{db_name} has no native JSON column type",
                    suggestion="Store as NVARCHAR(MAX) (SQL Server) or VARCHAR (Redshift); parse at app layer",
                    severity="warning"
                ))

            if canon == "JSONB" and db_name == "MySQL":
                notes.append(ColumnMigrationNote(
                    table=table.name, column=col.name,
                    issue="MySQL has JSON but not JSONB (binary JSON)",
                    suggestion="Use the JSON type; note performance characteristics differ from PostgreSQL JSONB",
                    severity="info"
                ))

            if canon == "ARRAY" and not prof.get("supports_array_type"):
                notes.append(ColumnMigrationNote(
                    table=table.name, column=col.name,
                    issue=f"{db_name} does not support ARRAY columns",
                    suggestion="Normalize into a separate child table with a FK back to this table",
                    severity="error"
                ))

            if canon == "GEOMETRY" and db_name not in ("PostgreSQL", "MySQL", "Redshift"):
                notes.append(ColumnMigrationNote(
                    table=table.name, column=col.name,
                    issue=f"GEOMETRY type has limited or no support in {db_name}",
                    suggestion="Store as WKT in a VARCHAR column or use a dedicated spatial DB",
                    severity="warning"
                ))

        if not prof.get("supports_fk"):
            for col in table.columns:
                if col.is_foreign_key and col.references:
                    ref = col.references
                    notes.append(ColumnMigrationNote(
                        table=table.name, column=col.name,
                        issue=f"FK to {ref['table']}.{ref['column']} — {db_name} does not enforce FK constraints",
                        suggestion="Enforce referential integrity in application code or periodic consistency checks",
                        severity="warning"
                    ))

    if prof.get("fk_disabled_by_default") and schema.foreign_keys_count > 0:
        notes.append(ColumnMigrationNote(
            table="(global)", column="(all FK columns)",
            issue="SQLite disables FK enforcement by default",
            suggestion="Run 'PRAGMA foreign_keys = ON;' at the start of every connection",
            severity="warning"
        ))

    if not prof.get("constraints_enforced", True) and (schema.foreign_keys_count > 0 or schema.primary_keys_count > 0):
        notes.append(ColumnMigrationNote(
            table="(global)", column="(all constraint columns)",
            issue="Redshift accepts FK/UNIQUE in DDL but does NOT enforce them at runtime",
            suggestion="Enforce constraints in your ETL pipeline or data quality layer",
            severity="warning"
        ))

    return notes


def _generate_migration_warnings(schema, prof, db_name, type_violations, special_frac):
    warnings = []
    if type_violations > 0:
        warnings.append(f"{type_violations} column type(s) need manual conversion — see column notes")
    if schema.foreign_keys_count > 0 and not prof.get("supports_fk"):
        warnings.append(f"{schema.foreign_keys_count} FK relationship(s) must be enforced in application code")
    if prof.get("fk_disabled_by_default") and schema.foreign_keys_count > 0:
        warnings.append("Run PRAGMA foreign_keys = ON at connection start (SQLite FK default is OFF)")
    if not prof.get("constraints_enforced", True):
        warnings.append("FK and UNIQUE constraints are informational only — not enforced at runtime")
    if schema.has_advanced_types and special_frac < 0.5:
        warnings.append("Advanced types (JSON/ARRAY/GEOMETRY) have limited support — check column notes")
    if db_name == "Cassandra" and schema.foreign_keys_count > 0:
        warnings.append("Cassandra is query-driven — FK-heavy relational schemas require significant redesign")
    if db_name in ("DynamoDB", "Cassandra") and schema.total_tables > 5:
        warnings.append(f"Migrating {schema.total_tables} normalized tables to {db_name} typically requires consolidation")
    if db_name == "Redshift" and schema.total_tables > 0:
        warnings.append("Redshift is OLAP — if this is a transactional schema, PostgreSQL is likely a better fit")
    if not warnings:
        warnings.append("No major migration blockers detected")
    return warnings


def _compute_verdict(absolute_pct: float, type_violations: int, has_critical_notes: bool) -> str:
    if absolute_pct >= 90 and not has_critical_notes:
        return "excellent"
    elif absolute_pct >= 75 and type_violations == 0:
        return "good"
    elif absolute_pct >= 55:
        return "fair"
    else:
        return "poor"


def score_schema(
    schema: ParsedSchema,
    db_features_path: str = "data/db_features.json",
    type_map: Dict[str, str] | None = None,
    weights: Dict[str, float] | None = None
) -> Dict[str, Any]:
    if type_map is None:
        type_map = CANONICAL_TYPE_MAP
    if weights is None:
        weights = DEFAULT_WEIGHTS

    if not schema.tables or schema.total_columns == 0:
        return {}

    profiles = _load_db_profiles(db_features_path)

    total_columns = schema.total_columns
    constraint_counts = {
        "pk": schema.primary_keys_count, "fk": schema.foreign_keys_count,
        "unique": 0, "not_null": 0,
    }
    special_counts = {"json": 0, "geometry": 0, "blob": 0, "array": 0}

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
            if canon == "ARRAY":
                special_counts["array"] += 1

    results = {}
    raw_scores = {}

    for db_name, prof in profiles.items():
        supported_cols = 0
        type_violations = 0

        for table in schema.tables:
            for col in table.columns:
                input_type = col.raw_type if col.raw_type else col.data_type
                canon, length, precision, scale = _parse_and_canonicalize_type(input_type)
                is_supported = _is_type_supported(canon, prof["supported_types"])

                if is_supported and length is not None and canon in ("VARCHAR", "CHAR"):
                    max_len = prof.get("varchar_max_length")
                    if max_len and length > max_len:
                        is_supported = False
                        type_violations += 1

                if is_supported and precision is not None and canon == "DECIMAL":
                    max_prec = prof.get("decimal_max_precision")
                    if max_prec and precision > max_prec:
                        is_supported = False
                        type_violations += 1

                if is_supported:
                    supported_cols += 1

        type_frac = supported_cols / total_columns if total_columns > 0 else 1.0
        if type_violations > 0:
            penalty = min(0.4, type_violations * 0.08)
            type_frac = max(0.0, type_frac * (1 - penalty))

        constraint_total = sum(constraint_counts.values()) or 1
        supported_constraints = (
            constraint_counts["pk"]
            + (constraint_counts["fk"] if prof.get("supports_fk") else 0)
            + (constraint_counts["unique"] if prof.get("supports_unique") else 0)
            + (constraint_counts["not_null"] if prof.get("supports_not_null") else 0)
        )
        constraint_frac = supported_constraints / constraint_total
        # Penalise DBs where constraints are accepted in DDL but not enforced at runtime
        if not prof.get("constraints_enforced", True) and constraint_total > 1:
            constraint_frac *= 0.65 

        special_total = sum(special_counts.values())
        if special_total > 0:
            special_supported = 0
            if special_counts["json"] > 0 and (
                "JSON" in prof["supported_types"] or "JSONB" in prof["supported_types"]
                or prof.get("supports_json_indexing")
            ):
                special_supported += special_counts["json"]
            if special_counts["geometry"] > 0 and "GEOMETRY" in prof["supported_types"]:
                special_supported += special_counts["geometry"]
            if special_counts["blob"] > 0 and any(t in prof["supported_types"] for t in ("BLOB", "BYTEA")):
                special_supported += special_counts["blob"]
            if special_counts["array"] > 0 and prof.get("supports_array_type"):
                special_supported += special_counts["array"]
            special_frac = special_supported / special_total
        else:
            readiness_weighted = [
                (prof.get("supports_transactions", False),     0.30),
                (prof.get("supports_window_functions", False), 0.25),
                (prof.get("supports_cte", False),              0.25),
                (prof.get("supports_stored_procs", False),     0.10),
                (prof.get("supports_concurrent_writes", True), 0.10),
            ]
            readiness_score = sum(w for supported, w in readiness_weighted if supported)

            if prof.get("is_embedded") and schema.foreign_keys_count > 0:
                readiness_score *= 0.82

            # OLAP DBs get penalized for transactional schemas — they are not designed
            # for row-level OLTP workloads regardless of type/constraint support
            if prof.get("is_olap") and schema.foreign_keys_count > 0:
                readiness_score *= 0.55

            special_frac = min(readiness_score, 1.0)

        raw = (
            weights["type_support"] * type_frac
            + weights["constraint_support"] * constraint_frac
            + weights["special_support"] * special_frac
        )

        col_notes = _generate_column_notes(schema, prof, db_name)
        has_critical = any(n.severity == "error" for n in col_notes)
        absolute_pct = round(raw * 100, 2)
        verdict = _compute_verdict(absolute_pct, type_violations, has_critical)
        migration_warnings = _generate_migration_warnings(schema, prof, db_name, type_violations, special_frac)

        raw_scores[db_name] = raw
        results[db_name] = {
            "raw_score": round(raw, 4),
            "absolute_pct": absolute_pct,
            "verdict": verdict,
            "explanation": {
                "type_support_frac": round(type_frac, 4),
                "type_violations": type_violations,
                "constraint_frac": round(constraint_frac, 4),
                "special_frac": round(special_frac, 4),
                "weights": weights,
                "migration_warnings": migration_warnings,
                "column_notes": [n.model_dump() for n in col_notes],
            },
        }

    total_raw = sum(raw_scores.values()) or 1.0
    for db_name in results:
        results[db_name]["relative_pct"] = round((raw_scores[db_name] / total_raw) * 100, 2)

    return dict(sorted(results.items(), key=lambda item: item[1]["raw_score"], reverse=True))