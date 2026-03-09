from __future__ import annotations
import csv
import io
import json
import argparse
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path
import re

import sqlglot
from sqlglot import exp


@dataclass
class Column:
    column_name: str
    data_type: str
    constraints: str


@dataclass
class Table:
    table_name: str
    columns: List[Column]


class SchemaParser:

    def __init__(self, input_file: str, input_format: str = "csv", dialect: Optional[str] = None):
        self.input_file = input_file
        self.input_format = input_format.lower()
        self.dialect = dialect

    def parse(self) -> List[Table]:
        if self.input_format == "csv":
            return self._parse_csv()
        elif self.input_format == "json":
            return self._parse_json()
        elif self.input_format == "sql":
            return self._parse_sql()
        else:
            raise ValueError(f"Unsupported format: {self.input_format}")

    # ------------------- CSV Parser -------------------
    def _parse_csv(self) -> List[Table]:
        tables: Dict[str, List[Column]] = {}
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
            parsed = parse_constraints_text(constraints_text)

            is_pk = parse_bool_token(explicit_is_pk) if explicit_is_pk is not None else parsed["is_pk"]
            is_fk = parse_bool_token(explicit_is_fk) if explicit_is_fk is not None else parsed["is_fk"]
            nullable = parse_bool_token(explicit_nullable) if explicit_nullable is not None else parsed["nullable"]

            ref_table = get_field(row, "ref_table", "references_table", "ref_tbl", default=None)
            ref_column = get_field(row, "ref_column", "references_column", "ref_col", default=None)
            references = {"table": ref_table.strip(), "column": ref_column.strip()} if ref_table and ref_column else None

            col = Column(column_name=col_name, data_type=data_type, constraints=constraints_text)
            setattr(col, "is_pk", is_pk)
            setattr(col, "is_fk", is_fk)
            setattr(col, "nullable", nullable)
            setattr(col, "row_estimate", None)
            setattr(col, "references", references)

            tables.setdefault(tname, []).append(col)

        return [Table(table_name=t, columns=c) for t, c in tables.items()]

    # ------------------- JSON Parser -------------------
    def _parse_json(self) -> List[Table]:
        with open(self.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return [Table(table_name=t["table_name"], columns=[Column(**col) for col in t["columns"]]) for t in data]

        if isinstance(data, dict) and "tables" in data:
            tables = []
            for tname, tdef in data["tables"].items():
                cols = []
                for c in tdef.get("columns", []):
                    cols.append(Column(
                        column_name=c.get("name") or c.get("column_name"),
                        data_type=c.get("type") or "TEXT",
                        constraints=c.get("constraints", "")
                    ))
                tables.append(Table(table_name=tname, columns=cols))
            return tables

        raise ValueError("Unsupported JSON format for schema input")

    # ------------------- SQL Parser-------------------
    def _parse_sql(self) -> List[Table]:
        path = Path(self.input_file)
        if not path.exists():
            raise FileNotFoundError(f"SQL file not found: {self.input_file}")

        sql_text = path.read_text(encoding="utf-8")
        tables_out: List[Table] = []

        create_table_regex = re.compile(
            r"CREATE\s+TABLE\s+([`\"\[\]\w]+)\s*\((.*?)\);",
            flags=re.IGNORECASE | re.DOTALL
        )

        def split_columns(block: str) -> List[str]:
            cols = []
            cur = []
            depth = 0
            for ch in block:
                if ch == "(":
                    depth += 1
                    cur.append(ch)
                elif ch == ")":
                    depth = max(depth - 1, 0)
                    cur.append(ch)
                elif ch == "," and depth == 0:
                    s = "".join(cur).strip()
                    if s:
                        cols.append(s)
                    cur = []
                else:
                    cur.append(ch)
            last = "".join(cur).strip()
            if last:
                cols.append(last)
            return cols

        for m in create_table_regex.finditer(sql_text):
            tname = m.group(1).strip("`\"[]")
            inner = m.group(2)
            col_texts = split_columns(inner)
            cols: List[Column] = []

            for ctext in col_texts:
                ctext = ctext.strip()
                # skip table-level constraints
                if re.match(r"^(PRIMARY|FOREIGN|UNIQUE|CONSTRAINT|CHECK)\b", ctext, flags=re.IGNORECASE):
                    continue
                parts = ctext.split(None, 1)
                if not parts:
                    continue
                cname = parts[0].strip("`\"[]")
                rest = parts[1] if len(parts) > 1 else ""
                tmatch = re.match(r"^([A-Za-z0-9_]+(\s*\([^\)]*\))?)", rest)
                dtype = tmatch.group(1).strip().upper() if tmatch else "TEXT"
                cons_txt = rest[len(tmatch.group(0)):].strip() if tmatch else rest

                is_pk = bool(re.search(r"\bPRIMARY\s+KEY\b", cons_txt, flags=re.IGNORECASE))
                is_fk = bool(re.search(r"\bREFERENCES\b", cons_txt, flags=re.IGNORECASE))
                nullable = not bool(re.search(r"\bNOT\s+NULL\b", cons_txt, flags=re.IGNORECASE))

                refm = re.search(r"REFERENCES\s+([`\"\[\]\w]+)\s*\(\s*([`\"\[\]\w]+)\s*\)", cons_txt, flags=re.IGNORECASE)
                references = {"table": refm.group(1).strip("`\"[]"), "column": refm.group(2).strip("`\"[]")} if refm else None

                col = Column(column_name=cname, data_type=dtype, constraints=cons_txt)
                setattr(col, "is_pk", is_pk)
                setattr(col, "is_fk", is_fk)
                setattr(col, "nullable", nullable)
                setattr(col, "references", references)
                cols.append(col)

            tables_out.append(Table(table_name=tname, columns=cols))

        if tables_out:
            print(f"[DEBUG] Extracted {len(tables_out)} tables: {[t.table_name for t in tables_out]}")
        else:
            print("⚠️ No CREATE TABLE statements found — check SQL file or dialect.")

        return tables_out

    def to_dict(self, tables: List[Table]) -> Dict[str, Any]:
        out = {}
        for table in tables:
            out[table.table_name] = {
                "table_name": table.table_name,
                "columns": []
            }
            for col in table.columns:
                out[table.table_name]["columns"].append({
                    "column_name": col.column_name,
                    "data_type": col.data_type,
                    "constraints": col.constraints,
                    "is_pk": getattr(col, "is_pk", False),
                    "is_fk": getattr(col, "is_fk", False),
                    "nullable": getattr(col, "nullable", True),
                    "references": getattr(col, "references", None)
                })
        return out


def _cli():
    ap = argparse.ArgumentParser(description="SchemaParser CLI (csv/json/sql -> canonical tables)")
    ap.add_argument("--input", "-i", required=True, help="Path to input file (CSV, JSON, or SQL)")
    ap.add_argument("--format", "-f", choices=["csv", "json", "sql"], default="csv", help="Input format")
    ap.add_argument("--dialect", "-d", default=None, help="SQL dialect (postgres, mysql, sqlite, oracle, etc.)")
    ap.add_argument("--out", "-o", help="Optional output JSON file for canonical schema")
    args = ap.parse_args()

    sp = SchemaParser(args.input, args.format, dialect=args.dialect)
    tables = sp.parse()

    pretty = json.dumps(sp.to_dict(tables), indent=2)
    print(pretty)
    if args.out:
        Path(args.out).write_text(pretty, encoding="utf-8")
        print("✅ Saved canonical schema to:", args.out)


if __name__ == "__main__":
    _cli()
