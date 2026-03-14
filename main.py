import argparse
import json
import sys
from pathlib import Path

from parser.schema_parser import SchemaParser
from core.models import ParsedSchema
from core.scorer import score_schema   
from core.schema_graph import SchemaGraph
from core.schema_complexity import SchemaComplexityAnalyzer
from core.schema_quality import SchemaQualityAnalyzer


def print_schema_human_readable(schema: ParsedSchema):
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
            type_display = col.data_type
            if col.length is not None:
                type_display += f"({col.length})"
            elif col.precision is not None and col.scale is not None:
                type_display += f"({col.precision},{col.scale})"
            elif col.precision is not None:
                type_display += f"({col.precision})"

            flags = []
            if col.is_primary_key: flags.append("PK")
            if col.is_foreign_key:
                ref = col.references or {}
                flags.append(f"FK→{ref.get('table','?')}.{ref.get('column','?')}")
            if col.is_unique: flags.append("UNIQUE")
            if not col.nullable: flags.append("NOT NULL")
            if col.default is not None: flags.append(f"DEFAULT {col.default}")
            
            flags_str = " | ".join(flags) if flags else "—"
            constraints_extra = ", ".join(col.constraints) if col.constraints else ""
            if constraints_extra and constraints_extra != flags_str:
                flags_str += f"  ({constraints_extra})"
            
            print(f"  • {col.name:25} {type_display:20}  [{flags_str}]")
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
        graph_engine = SchemaGraph(schema)
        graph_engine.build_graph()

        print("\nSchema Graph Metrics")
        print("-" * 40)

        print("Dependency depth:", graph_engine.dependency_depth())
        print("Join density:", round(graph_engine.join_density(), 3))

        cycles = graph_engine.detect_cycles()
        print("Cycles:", cycles if cycles else "None")

        print("Migration order:", graph_engine.migration_order())

        complexity = SchemaComplexityAnalyzer(schema)

        print("\nSchema Complexity Analysis")
        print("-" * 40)

        print("Tables:", complexity.table_count())
        print("Foreign Keys:", complexity.foreign_key_count())
        print("Join Density:", round(complexity.join_density(), 3))
        print("Dependency Depth:", complexity.dependency_depth())
        print("Hub Tables:", complexity.hub_tables() or "None")
        print("Fanout Tables:", complexity.fanout_tables() or "None")
        print("Complexity Score:", complexity.complexity_score())

        quality = SchemaQualityAnalyzer(schema)

        print("\nSchema Quality Analysis")
        print("-" * 40)

        print("Tables without PK:", quality.tables_without_primary_keys() or "None")
        print("FK without index:", quality.fk_without_index() or "None")
        print("Weak tables:", quality.weak_tables() or "None")
        print("Quality score:", quality.quality_score(), "/ 10")
    
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

            for db_name, info in scoring_results.items():
                abs_pct = info.get("absolute_pct", 0)
                rel_pct = info.get("relative_pct", 0)
                expl = info.get("explanation", {})  

                print(f"{db_name:18} {abs_pct:5.1f}% abs  |  {rel_pct:5.1f}% rel")

                type_str = f"   Types: {expl.get('type_support_frac', 0):.4f}"
                if expl.get("type_violations", 0) > 0:
                    type_str += f" (after penalty) | type_violations: {expl['type_violations']}"
                print(type_str)

                print(f"   Constraints: {expl.get('constraint_frac', 0):.4f}  | Special: {expl.get('special_frac', 0):.4f}")

                print("   Migration Warnings:")
                warnings = expl.get("migration_warnings", ["No major migration blockers"])
                for w in warnings:
                    print(f"      {w}")
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