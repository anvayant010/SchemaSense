import argparse
import json
import sys
from pathlib import Path

from parser.schema_parser import SchemaParser
from core.models import ParsedSchema
from core.scorer import score_schema   


def print_schema_human_readable(schema: ParsedSchema):
    """Print a clean, readable view of the parsed schema"""
    print("\n" + "=" * 70)
    print("Parsed Schema Overview")
    print("=" * 70)
    
    if not schema.tables:
        print("No tables found in schema.")
        return

    for table in schema.tables:
        print(f"\nTable: {table.name}")
        print("-" * 60)
        for col in table.columns:
            flags = []
            if col.is_primary_key:
                flags.append("PK")
            if col.is_foreign_key:
                ref = col.references or {}
                flags.append(f"FK → {ref.get('table', '?')}.{ref.get('column', '?')}")
            if col.is_unique:
                flags.append("UNIQUE")
            if not col.nullable:
                flags.append("NOT NULL")
            if col.default is not None:
                flags.append(f"DEFAULT {col.default}")
            
            flags_str = " | ".join(flags) if flags else "—"
            constraints_extra = ", ".join(col.constraints) if col.constraints else ""
            if constraints_extra and constraints_extra != flags_str:
                flags_str += f"  ({constraints_extra})"
            
            print(f"  • {col.name:25} {col.data_type:15}  [{flags_str}]")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="SchemaSense: Parse → Analyze → Score Database Schema Compatibility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input schema file (CSV, SQL, or JSON)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json", "sql"],
        required=True,
        help="Input format"
    )
    parser.add_argument(
        "--out", "-o",
        default=None,
        help="Save parsed canonical schema as JSON (optional)"
    )
    parser.add_argument(
        "--db-features", "-d",
        default="data/db_features.json",
        help="Path to DBMS capabilities JSON"
    )
    parser.add_argument(
        "--score-out", "-s",
        default=None,
        help="Save scoring results as JSON (optional)"
    )
    parser.add_argument(
        "--dialect", "-t",
        default=None,
        help="SQL dialect hint (postgres, mysql, sqlite, etc.)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show more detailed output (future use)"
    )

    args = parser.parse_args()

    # Parse the schema
    print(f"\nParsing schema: {args.input} (format: {args.format})")

    try:
        schema_parser = SchemaParser(
            input_file=args.input,
            input_format=args.format,
            dialect=args.dialect
        )
        schema: ParsedSchema = schema_parser.parse()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Parsing failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected parsing error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    print_schema_human_readable(schema)

    print("\nQuick Summary:")
    print(json.dumps(schema.to_summary_dict(), indent=2))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(schema.model_dump_json(indent=2))
        print(f"\nSaved parsed schema → {out_path.resolve()}")

    db_features_path = Path(args.db_features)
    if not db_features_path.is_file():
        print(f"\nWarning: DB features file not found → {db_features_path}")
        print("Scoring skipped. Use --db-features to specify a valid path.")
    else:
        print(f"\nLoading DB capabilities from: {db_features_path}")
        try:
            scoring_results = score_schema(schema, db_features_path=str(db_features_path))

            print("\n" + "=" * 70)
            print("Database Suitability Ranking")
            print("=" * 70)

            for db_name, info in sorted(scoring_results.items(), key=lambda x: x[1].get("absolute_pct", 0), reverse=True):
                abs_pct = info.get("absolute_pct", 0)
                rel_pct = info.get("relative_pct", 0)
                expl = info.get("explanation", {})
                tfrac = expl.get("type_support_frac", "?")
                cfrac = expl.get("constraint_frac", "?")
                sfrac = expl.get("special_frac", "?")

                print(f"{db_name:18} {abs_pct:5.1f}% abs  |  {rel_pct:5.1f}% rel")
                print(f"   Types: {tfrac:>5} | Constraints: {cfrac:>5} | Special: {sfrac:>5}")
                print()

            if args.score_out:
                score_path = Path(args.score_out)
                score_path.parent.mkdir(parents=True, exist_ok=True)
                with open(score_path, "w", encoding="utf-8") as f:
                    json.dump(scoring_results, f, indent=2)
                print(f"Saved scoring results → {score_path.resolve()}")

        except Exception as e:
            print(f"Scoring failed: {type(e).__name__}: {e}", file=sys.stderr)


    print("\nDone.\n")


if __name__ == "__main__":
    main()