from __future__ import annotations
import json
import re
import argparse
from typing import List, Dict, Any, Tuple, Optional

DEFAULT_WEIGHTS = {
    "type_support": 0.60,
    "constraint_support": 0.25,
    "special_support": 0.15
}

_type_regex = re.compile(r"^([a-zA-Z0-9_]+)\s*(?:\(\s*([0-9]+)\s*(?:,\s*([0-9]+)\s*)?\))?$")

CANONICAL_TYPE_MAP = {
    "INT": "INT", "INTEGER": "INT", "SMALLINT": "SMALLINT", "BIGINT": "BIGINT",
    "NUMBER": "DECIMAL", "NUMERIC": "DECIMAL", "DECIMAL": "DECIMAL", "FLOAT": "FLOAT", "DOUBLE": "DOUBLE",
    "VARCHAR": "VARCHAR", "VARCHAR2": "VARCHAR", "NVARCHAR2": "VARCHAR", "CHAR": "CHAR", "TEXT": "TEXT", "CLOB": "CLOB",
    "BLOB": "BLOB", "BYTEA": "BLOB",
    "DATE": "DATE", "TIMESTAMP": "TIMESTAMP", "DATETIME": "TIMESTAMP",
    "JSON": "JSON", "JSONB": "JSON", "DOCUMENT": "DOCUMENT",
    "BOOLEAN": "BOOLEAN", "UUID": "UUID", "GEOMETRY": "GEOMETRY"
}

def _parse_type(type_str: Optional[str]) -> Tuple[str, int]:
    """Return (base_type_upper, length_or_precision_or_0)."""
    if not type_str:
        return ("TEXT", 0)
    s = str(type_str).strip().upper()
    m = _type_regex.match(s)
    if not m:
        return (s, 0)
    base = m.group(1)
    length = m.group(2)
    if length:
        try:
            return (base, int(length))
        except Exception:
            return (base, 0)
    return (base, 0)

def _canonicalize(base_type: str, type_map: Dict[str,str]) -> str:
    b = base_type.upper()
    return type_map.get(b, b)

def _load_db_profiles(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    profiles = {}
    for db, prof in data.items():
        p = dict(prof) 
        supp = prof.get("supported_types", [])
        p["supported_types"] = set([str(x).strip().upper() for x in supp])
        for k in ("supports_fk", "supports_unique", "supports_check", "supports_json_indexing",
                  "supports_partitioning", "supports_stored_procs"):
            if k not in p:
                p[k] = False
        profiles[db] = p
    return profiles

def score_schema(tables: List[Any],
                 db_features_path: str = "data/db_features.json",
                 type_map: Dict[str,str] = None,
                 weights: Dict[str, float] = None) -> Dict[str, Any]:
   
    if type_map is None:
        type_map = CANONICAL_TYPE_MAP
    if weights is None:
        weights = DEFAULT_WEIGHTS

    profiles = _load_db_profiles(db_features_path)

    # Gather schema stats
    total_columns = 0
    type_counts: Dict[str,int] = {}
    constraint_counts = {"pk":0, "fk":0, "unique":0, "not_null":0}
    special_counts = {"json":0, "geometry":0, "blob":0}

    for table in tables:
        for col in table.columns:
            total_columns += 1
            base, length = _parse_type(getattr(col, "data_type", getattr(col, "type", None)))
            canon = _canonicalize(base, type_map)
            type_counts[canon] = type_counts.get(canon, 0) + 1

            is_pk = bool(getattr(col, "is_pk", False))
            is_fk = bool(getattr(col, "is_fk", False))
            not_null = not bool(getattr(col, "nullable", True))
            is_unique = False
            cons_txt = getattr(col, "constraints", None) or getattr(col, "comment", "") or ""
            if isinstance(cons_txt, str) and "unique" in cons_txt.lower():
                is_unique = True

            if is_pk: constraint_counts["pk"] += 1
            if is_fk: constraint_counts["fk"] += 1
            if is_unique: constraint_counts["unique"] += 1
            if not_null: constraint_counts["not_null"] += 1

            if canon in ("JSON", "DOCUMENT", "JSONB"):
                special_counts["json"] += 1
            if canon in ("GEOMETRY",):
                special_counts["geometry"] += 1
            if canon in ("BLOB", "BYTEA", "CLOB"):
                special_counts["blob"] += 1

    if total_columns == 0:
        return {}

    # Score each DB
    results: Dict[str, Any] = {}
    raw_scores: Dict[str, float] = {}

    for dbname, prof in profiles.items():
      
        supported_cols = 0
        for tname, cnt in type_counts.items():
            if tname in prof["supported_types"]:
                supported_cols += cnt
            else:
                pass
        type_support_frac = supported_cols / total_columns

        # constraint support
        constraint_total = sum(constraint_counts.values())
        if constraint_total == 0:
            constraint_frac = 1.0
        else:
            supported_constraints = 0
            if prof.get("supports_fk", False):
                supported_constraints += constraint_counts["fk"]
            if prof.get("supports_unique", True):
                supported_constraints += constraint_counts["unique"]
            supported_constraints += constraint_counts["pk"]
            supported_constraints += constraint_counts["not_null"]
            constraint_frac = supported_constraints / constraint_total if constraint_total > 0 else 1.0

        # special features (JSON, GEOMETRY, BLOB)
        special_total = sum(special_counts.values()) or 1
        special_supported = 0
        if special_counts["json"] > 0:
            if prof.get("supports_json_indexing", False) or ("JSON" in prof.get("supported_types", set())):
                special_supported += special_counts["json"]
        if special_counts["geometry"] > 0 and ("GEOMETRY" in prof.get("supported_types", set())):
            special_supported += special_counts["geometry"]
        if special_counts["blob"] > 0 and (("BLOB" in prof.get("supported_types", set())) or ("BYTEA" in prof.get("supported_types", set()))):
            special_supported += special_counts["blob"]
        special_frac = special_supported / special_total

        raw = (weights["type_support"] * type_support_frac +
               weights["constraint_support"] * constraint_frac +
               weights["special_support"] * special_frac)

        explanation = {
            "type_support_frac": round(type_support_frac, 4),
            "constraint_frac": round(constraint_frac, 4),
            "special_frac": round(special_frac, 4),
            "weights": weights
        }

        raw_scores[dbname] = raw
        results[dbname] = {
            "raw_score": raw,
            "absolute_pct": round(raw * 100, 2),
            "explanation": explanation
        }

    # Relative percentages
    total_raw = sum(raw_scores.values()) or 1.0
    for dbname in results:
        rel = raw_scores[dbname] / total_raw * 100.0
        results[dbname]["relative_pct"] = round(rel, 2)

    sorted_results = dict(sorted(results.items(), key=lambda kv: kv[1]["raw_score"], reverse=True))
    return sorted_results

def _load_parsed_schema_from_json(path: str):
    """Expect canonical JSON by-table format: { "table_name": { "columns":[{...},...] }, ... }"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tables = []
    class _C:
        pass
    for tname, tdef in data.items():
        tbl = _C()
        cols = []
        for c in tdef.get("columns", []):
            col = _C()
            col.data_type = c.get("data_type") or c.get("type") or c.get("column_type") or c.get("dataType")
            col.constraints = c.get("constraints") or ""
            col.is_pk = c.get("is_pk", False)
            col.is_fk = c.get("is_fk", False)
            col.nullable = c.get("nullable", True)
            col.comment = c.get("comment", "")
            cols.append(col)
        tbl.columns = cols
        tbl.table_name = tname
        tables.append(tbl)
    return tables

def main(argv=None):
    ap = argparse.ArgumentParser(description="Score parsed schema against DB profiles (JSON)")
    ap.add_argument("--parsed", "-p", required=True, help="Parsed canonical schema JSON (by-table dict)")
    ap.add_argument("--db-features", "-d", default="data/db_features.json", help="DB features JSON path")
    ap.add_argument("--out", "-o", help="Optional scoring output JSON path")
    args = ap.parse_args(argv)

    tables = _load_parsed_schema_from_json(args.parsed)
    results = score_schema(tables, db_features_path=args.db_features)
    print(json.dumps(results, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"Wrote scoring results to {args.out}")

if __name__ == "__main__":
    main()
