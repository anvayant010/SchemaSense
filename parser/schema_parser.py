from __future__ import annotations
import csv
import io
import json
import argparse
from typing import List, Dict, Optional
from pathlib import Path
import re

from core.models import ParsedSchema, Table, Column, Index
from core.scorer import _parse_and_canonicalize_type

import sqlglot  
from sqlglot import exp


class SchemaParser:

    def __init__(self, input_file: str, input_format: str = "csv", dialect: Optional[str] = None):
        self.input_file = input_file
        self.input_format = input_format.lower()
        self.dialect = dialect

    def parse(self) -> ParsedSchema:
        if self.input_format == "csv":
            return self._parse_csv()
        elif self.input_format == "json":
            return self._parse_json()
        elif self.input_format == "sql":
            return self._parse_sql()
        else:
            raise ValueError(f"Unsupported format: {self.input_format}")

    # ------------------- CSV Parser -------------------
    def _parse_csv(self) -> ParsedSchema:
        tables_dict: Dict[str, List[Column]] = {}

        with open(self.input_file, "r", encoding="utf-8") as f:
            raw = f.read()

        reader_for_headers = csv.DictReader(io.StringIO(raw))
        headers = reader_for_headers.fieldnames or []
        normalized_map = {h.strip().lower(): h for h in headers if h}

        def get_field(row, *variants, default=None):
            for v in variants:
                k = v.lower()
                if k in normalized_map:
                    return row.get(normalized_map[k], default)
            return default

        def parse_bool_token(val):
            if val is None:
                return False
            v = str(val).strip().lower()
            return v in ("1", "true", "yes", "y", "t")

        def parse_constraints_text(ctxt: str):
            c = (ctxt or "").strip().lower()
            flags = {"is_pk": False, "is_fk": False, "nullable": True}
            if "primary key" in c or c == "pk":
                flags["is_pk"] = True
                flags["nullable"] = False
            if "foreign key" in c or c == "fk":
                flags["is_fk"] = True
            if "not null" in c or "not_null" in c or "non-null" in c:
                flags["nullable"] = False
            return flags

        for row in csv.DictReader(io.StringIO(raw)):
            tname = get_field(row, "table_name", "table", "tbl", "table-name")
            if not tname:
                continue
            tname = tname.strip()

            col_name = get_field(row, "column_name", "column", "col", "field")
            if not col_name:
                continue
            col_name = col_name.strip()

            data_type = get_field(row, "data_type", "type", "data-type", default="TEXT") or "TEXT"
            data_type = data_type.strip().upper()

            explicit_is_pk = get_field(row, "is_pk", "pk", "primary_key")
            explicit_is_fk = get_field(row, "is_fk", "fk", "foreign_key")
            explicit_nullable = get_field(row, "nullable", "is_nullable", default=None)

            constraints_text = (get_field(row, "constraints", "constraint", default="") or "").strip()
            parsed_flags = parse_constraints_text(constraints_text)

            is_pk = parse_bool_token(explicit_is_pk) if explicit_is_pk is not None else parsed_flags["is_pk"]
            is_fk = parse_bool_token(explicit_is_fk) if explicit_is_fk is not None else parsed_flags["is_fk"]
            nullable = parse_bool_token(explicit_nullable) if explicit_nullable is not None else parsed_flags["nullable"]

            ref_table = get_field(row, "ref_table", "references_table", "ref_tbl")
            ref_column = get_field(row, "ref_column", "references_column", "ref_col")
            references = None
            if ref_table and ref_column:
                references = {
                    "table": ref_table.strip(),
                    "column": ref_column.strip()
                }

            canon_type, length, precision, scale = _parse_and_canonicalize_type(data_type)  

            column = Column(
                name=col_name,
                data_type=canon_type,          
                raw_type=data_type,            
                length=length,
                precision=precision,
                scale=scale,
                nullable=nullable,
                is_primary_key=is_pk,
                is_foreign_key=is_fk,
                is_unique=False,               
                references=references,
                constraints=[constraints_text] if constraints_text else []
            )

            tables_dict.setdefault(tname, []).append(column)

        tables = [
            Table(name=table_name, columns=columns)
            for table_name, columns in tables_dict.items()
        ]

        return ParsedSchema(
            tables=tables,
            source_format="csv",
            source_file=self.input_file
        )

    # ------------------- JSON Parser -------------------
    def _parse_json(self) -> ParsedSchema:
        with open(self.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        tables: List[Table] = []

        if isinstance(data, list):
            for t in data:
                tname = t.get("table_name") or t.get("name")
                if not tname:
                    continue
                cols = []
                for c in t.get("columns", []):
                    cols.append(Column(
                        name=c.get("name") or c.get("column_name"),
                        data_type=c.get("type") or c.get("data_type", "TEXT"),
                        raw_type=c.get("type") or c.get("data_type"),
                        constraints=c.get("constraints", []) if isinstance(c.get("constraints"), list) else [c.get("constraints", "")]
                    ))
                tables.append(Table(name=tname, columns=cols))

        elif isinstance(data, dict) and "tables" in data:
            for tname, tdef in data["tables"].items():
                cols = []
                for c in tdef.get("columns", []):
                    cols.append(Column(
                        name=c.get("name") or c.get("column_name"),
                        data_type=c.get("type") or c.get("data_type", "TEXT"),
                        raw_type=c.get("type") or c.get("data_type"),
                        constraints=c.get("constraints", []) if isinstance(c.get("constraints"), list) else [c.get("constraints", "")]
                    ))
                tables.append(Table(name=tname, columns=cols))

        else:
            raise ValueError("Unsupported JSON schema format")

        return ParsedSchema(
            tables=tables,
            source_format="json",
            source_file=self.input_file
        )

    # ------------------- SQL Parser -------------------
    def _parse_sql(self) -> ParsedSchema:

        path = Path(self.input_file)

        if not path.exists():
            raise FileNotFoundError(f"SQL file not found: {self.input_file}")

        sql_text = path.read_text(encoding="utf-8")

        tables: Dict[str, List[Column]] = {}
        indexes = []

        try:
            dialect = self.dialect or "mysql"
            parsed_statements = sqlglot.parse(sql_text, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN)
        except Exception:
            parsed_statements = sqlglot.parse(sql_text, error_level=sqlglot.ErrorLevel.WARN)

        def _clean_name(raw: str) -> str:
            """Strip quotes and backticks from identifiers."""
            return raw.strip().strip("`\"'[]").strip()

        def _extract_fks_from_create(stmt) -> list[dict]:
            """Extract FK definitions from a CREATE TABLE statement."""
            fks = []
            for fk in stmt.find_all(exp.ForeignKey):
                fk_cols = [_clean_name(e.name) for e in fk.expressions]
                ref = fk.args.get("reference")
                if not (ref and ref.this):
                    continue
                try:
                    ref_table_node = ref.this.this
                    if hasattr(ref_table_node, "this"):
                        ref_table = _clean_name(ref_table_node.this.name if hasattr(ref_table_node.this, "name") else str(ref_table_node.this))
                    else:
                        ref_table = _clean_name(str(ref_table_node))
                    ref_cols = [_clean_name(e.name) for e in ref.this.expressions]
                    if fk_cols and ref_cols and ref_table:
                        for i, fk_col in enumerate(fk_cols):
                            ref_col = ref_cols[i] if i < len(ref_cols) else ref_cols[0]
                            fks.append({"fk_col": fk_col, "ref_table": ref_table, "ref_col": ref_col})
                except Exception:
                    continue
            return fks

        for stmt in parsed_statements:
            if stmt is None:
                continue

            # ---------------- CREATE TABLE ----------------
            if isinstance(stmt, exp.Create) and stmt.args.get("kind") == "TABLE":
                try:
                    tbl_node = stmt.this
                    raw_table_name = tbl_node.name if tbl_node.name else ""
                    if not raw_table_name and hasattr(tbl_node, "this"):
                        raw_table_name = tbl_node.this.name if hasattr(tbl_node.this, "name") else str(tbl_node.this)
                except Exception:
                    raw_table_name = ""
                table_name = _clean_name(raw_table_name)
                if "." in table_name:
                    table_name = table_name.split(".")[-1].strip()
                if not table_name:
                    continue

                columns = []

                for col in stmt.find_all(exp.ColumnDef):
                    col_name = _clean_name(col.name)
                    col_type = "TEXT"
                    if col.args.get("kind"):
                        col_type = col.args["kind"].sql()

                    canon_type, length, precision, scale = _parse_and_canonicalize_type(col_type)

                    nullable = True
                    is_pk = False
                    is_unique = False
                    is_fk = False
                    references = None
                    default = None
                    constraints = []

                    for c in col.args.get("constraints", []):
                        if isinstance(c, exp.ColumnConstraint):
                            kind = c.kind
                            if isinstance(kind, exp.PrimaryKeyColumnConstraint):
                                is_pk = True
                                nullable = False
                            elif isinstance(kind, exp.NotNullColumnConstraint):
                                nullable = False
                            elif isinstance(kind, exp.UniqueColumnConstraint):
                                is_unique = True
                            elif isinstance(kind, exp.DefaultColumnConstraint):
                                try:
                                    default = c.this.sql()
                                except Exception:
                                    default = None
                            elif isinstance(kind, exp.Reference):
                                is_fk = True
                                try:
                                    ref_tbl = _clean_name(kind.this.this.name if hasattr(kind.this, "this") else str(kind.this))
                                    ref_cols_expr = kind.this.expressions if hasattr(kind.this, "expressions") else []
                                    ref_col_name = _clean_name(ref_cols_expr[0].name) if ref_cols_expr else col_name
                                    references = {"table": ref_tbl, "column": ref_col_name}
                                except Exception:
                                    pass
                        elif isinstance(c, (exp.PrimaryKeyColumnConstraint, exp.PrimaryKey)):
                            is_pk = True
                            nullable = False
                        elif isinstance(c, exp.NotNullColumnConstraint):
                            nullable = False
                        elif isinstance(c, exp.UniqueColumnConstraint):
                            is_unique = True

                        try:
                            constraints.append(c.sql())
                        except Exception:
                            pass

                    columns.append(Column(
                        name=col_name,
                        data_type=canon_type,
                        raw_type=col_type,
                        length=length,
                        precision=precision,
                        scale=scale,
                        nullable=nullable,
                        is_primary_key=is_pk,
                        is_foreign_key=is_fk,
                        is_unique=is_unique,
                        references=references,
                        constraints=constraints,
                        default=default
                    ))

                for fk_info in _extract_fks_from_create(stmt):
                    for col in columns:
                        if col.name == fk_info["fk_col"]:
                            col.is_foreign_key = True
                            col.references = {"table": fk_info["ref_table"], "column": fk_info["ref_col"]}
                            break

                tables[table_name] = columns

            elif isinstance(stmt, exp.AlterTable):
                try:
                    alter_table_name = _clean_name(stmt.this.sql())
                    if "." in alter_table_name:
                        alter_table_name = alter_table_name.split(".")[-1].strip()

                    for action in stmt.args.get("actions", []):
                        if isinstance(action, exp.AddConstraint):
                            for constraint in action.expressions:
                                if isinstance(constraint, exp.ForeignKey):
                                    fk_cols = [_clean_name(e.name) for e in constraint.expressions]
                                    ref = constraint.args.get("reference")
                                    if not (ref and ref.this):
                                        continue
                                    try:
                                        ref_table_node = ref.this.this
                                        if hasattr(ref_table_node, "this"):
                                            ref_table = _clean_name(str(ref_table_node.this) if not hasattr(ref_table_node.this, "name") else ref_table_node.this.name)
                                        else:
                                            ref_table = _clean_name(str(ref_table_node))
                                        ref_cols = [_clean_name(e.name) for e in ref.this.expressions]
                                        if alter_table_name in tables:
                                            for i, fk_col in enumerate(fk_cols):
                                                ref_col = ref_cols[i] if i < len(ref_cols) else ref_cols[0]
                                                for col in tables[alter_table_name]:
                                                    if col.name == fk_col:
                                                        col.is_foreign_key = True
                                                        col.references = {"table": ref_table, "column": ref_col}
                                                        break
                                    except Exception:
                                        continue
                except Exception:
                    pass
            elif isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Index):
                try:
                    index_name = _clean_name(stmt.this.name)
                    tbl = stmt.args.get("table")
                    tbl_name = _clean_name(tbl.name) if tbl else None
                    cols = [_clean_name(e.name) for e in stmt.this.expressions if hasattr(e, "name")]
                    indexes.append(Index(
                        name=index_name,
                        table=tbl_name,
                        columns=cols,
                        unique=bool(stmt.args.get("unique", False))
                    ))
                except Exception:
                    pass

        table_list = [Table(name=name, columns=cols) for name, cols in tables.items()]

        return ParsedSchema(
            tables=table_list,
            source_format="sql",
            source_file=self.input_file,
            indexes=indexes
        )


def _cli():
    ap = argparse.ArgumentParser(description="SchemaSense Parser - Parse schema files to canonical format")
    ap.add_argument("--input", "-i", required=True, help="Path to input file (CSV, JSON, or SQL)")
    ap.add_argument("--format", "-f", choices=["csv", "json", "sql"], required=True, help="Input format")
    ap.add_argument("--dialect", "-d", default=None, help="SQL dialect (for future sqlglot usage)")
    ap.add_argument("--out", "-o", help="Optional: Save parsed schema as JSON")
    args = ap.parse_args()

    parser = SchemaParser(args.input, args.format, dialect=args.dialect)
    schema: ParsedSchema = parser.parse()

    print("Schema Summary:")
    print(json.dumps(schema.to_summary_dict(), indent=2))

    json_output = schema.model_dump_json(indent=2)
    print("\nFull Parsed Schema:")
    print(json_output)

    if args.out:
        Path(args.out).write_text(json_output, encoding="utf-8")
        print(f"\nSaved parsed schema to: {args.out}")


if __name__ == "__main__":
    _cli()