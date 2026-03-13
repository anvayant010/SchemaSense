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

        tables = []
        indexes = []

        parsed_statements = sqlglot.parse(sql_text)

        # print("Parsed statements:")
        # for s in parsed_statements:
        #     print(type(s), s.sql())

        for stmt in parsed_statements:

            # ---------------- TABLE PARSING ----------------
            if isinstance(stmt, exp.Create) and stmt.args.get("kind") == "TABLE":

                table_name = stmt.this.sql().replace("`", "").replace('"', "")
                columns = []

                columns_ast = list(stmt.find_all(exp.ColumnDef))

                for col in columns_ast:

                    col_name = col.name

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
                            if isinstance(c.kind, exp.PrimaryKeyColumnConstraint):
                                is_pk = True
                                nullable = False
                            elif isinstance(c.kind, exp.NotNullColumnConstraint):
                                nullable = False
                            elif isinstance(c.kind, exp.UniqueColumnConstraint):
                                is_unique = True
                            elif isinstance(c.kind, exp.DefaultColumnConstraint):
                                default = c.this.sql()
                        elif isinstance(c, (exp.PrimaryKeyColumnConstraint, exp.PrimaryKey)):
                            is_pk = True
                            nullable = False
                        elif isinstance(c, exp.NotNullColumnConstraint):
                            nullable = False
                        elif isinstance(c, exp.UniqueColumnConstraint):
                            is_unique = True
                        elif isinstance(c, exp.DefaultColumnConstraint):
                            default = c.this.sql()

                        constraints.append(c.sql())
                        

                    column = Column(
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
                    )

                    columns.append(column)

                for fk in stmt.find_all(exp.ForeignKey):
                    fk_columns = [e.name for e in fk.expressions]
                    
                    ref = fk.args.get('reference')
                    if ref and ref.this and ref.this.expressions:
                        ref_table = ref.this.this.this.name if ref.this.this and ref.this.this.this else None
                        ref_columns = [e.name for e in ref.this.expressions]
                        
                        if fk_columns and ref_columns and ref_table:
                            fk_column = fk_columns[0]
                            ref_column = ref_columns[0]
                            
                            for col in columns:
                                if col.name == fk_column:
                                    col.is_foreign_key = True
                                    col.references = {
                                        "table": ref_table,
                                        "column": ref_column
                                    }
                                    break

                tables.append(Table(name=table_name, columns=columns))
                

            # ---------------- INDEX PARSING ----------------
            if isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Index):

                index_name = stmt.this.name
                table = stmt.args.get("table")

                table_name = table.name if table else None

                cols = []
                for e in stmt.this.expressions:
                    cols.append(e.name)

                indexes.append(
                    Index(
                        name=index_name,
                        table=table_name,
                        columns=cols,
                        unique=stmt.args.get("unique", False)
                    )
                )

        return ParsedSchema(
            tables=tables,
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

    # Print summary
    print("Schema Summary:")
    print(json.dumps(schema.to_summary_dict(), indent=2))

    # Full JSON output
    json_output = schema.model_dump_json(indent=2)
    print("\nFull Parsed Schema:")
    print(json_output)

    if args.out:
        Path(args.out).write_text(json_output, encoding="utf-8")
        print(f"\nSaved parsed schema to: {args.out}")


if __name__ == "__main__":
    _cli()