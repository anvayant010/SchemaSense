import argparse
from parser.schema_parser import SchemaParser
import json
from core.scorer import score_schema


def main():
    parser = argparse.ArgumentParser(description="Database Schema Parser Tool + Scorer")
    parser.add_argument("--input", "-i", required=True, help="Input schema file path (CSV, JSON, or SQL)")
    parser.add_argument("--format", "-f", choices=["csv", "json", "sql"], default="csv", help="Input file format")
    parser.add_argument("--out", "-o", help="Output parsed schema JSON file (optional)")
    parser.add_argument("--db-features", "-d", default="data/db_features.json", help="DB features JSON file (default: data/db_features.json)")
    parser.add_argument("--score-out", "-s", help="Save scoring results JSON to this file (optional)")
    parser.add_argument("--dialect", "-t", default=None, help="SQL dialect (postgres, mysql, sqlite, etc.)")
    args = parser.parse_args()

    schema_parser = SchemaParser(args.input, args.format, dialect=args.dialect)
    tables = schema_parser.parse()

    print("\n Parsed Schema:\n")
    for table in tables:
        print(f"Table: {table.table_name}")
        for col in table.columns:
            flags = []
            if getattr(col, "is_pk", False):
                flags.append("PRIMARY KEY")
            if getattr(col, "is_fk", False):
                flags.append("FOREIGN KEY")
            if not getattr(col, "nullable", True):
                flags.append("NOT NULL")
            flags_str = ", ".join(flags) if flags else getattr(col, "constraints", "")
            print(f"  - {col.column_name} ({col.data_type}) [{flags_str}]")
        print()

    # Save parsed schema JSON if requested
    if args.out:
        output_dict = {}
        for table in tables:
            output_dict[table.table_name] = {
                "table_name": table.table_name,
                "columns": [
                    {
                        "column_name": col.column_name,
                        "data_type": col.data_type,
                        "constraints": col.constraints,
                        "is_pk": getattr(col, "is_pk", False),
                        "is_fk": getattr(col, "is_fk", False),
                        "nullable": getattr(col, "nullable", True),
                        "row_estimate": getattr(col, "row_estimate", None),
                        "references": getattr(col, "references", None)
                    } for col in table.columns
                ]
            }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(output_dict, f, indent=4)
        print(f"\nParsed schema saved to: {args.out}")

    try:
        scoring_results = score_schema(tables, db_features_path=args.db_features)
    except FileNotFoundError:
        print(f"\nDB features file not found: {args.db_features}")
        print("Provide a valid --db-features path (default: data/db_features.json).")
        return
    except Exception as e:
        print(f"\nError while scoring schema: {e}")
        return

    print("\nDatabase suitability ranking (absolute % / relative %):\n")
    for dbname, info in scoring_results.items():
        abs_pct = info.get("absolute_pct")
        rel_pct = info.get("relative_pct")
        expl = info.get("explanation", {})
        tfrac = expl.get("type_support_frac")
        cfrac = expl.get("constraint_frac")
        sfrac = expl.get("special_frac")
        print(f"{dbname}: {abs_pct}% absolute  |  {rel_pct}% relative")
        print(f"   (types={tfrac}, constraints={cfrac}, special={sfrac})\n")

    if args.score_out:
        with open(args.score_out, "w", encoding="utf-8") as f:
            json.dump(scoring_results, f, indent=2)
        print(f"Scoring results saved to: {args.score_out}")


if __name__ == "__main__":
    main()
