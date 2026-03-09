# SchemaSense

**SchemaSense** is an intelligent database schema analysis and suitability scoring tool that helps developers, architects, and teams evaluate how well a given database schema fits different database management systems (PostgreSQL, MySQL, SQLite, MongoDB, Oracle, etc.).

It parses schemas from multiple formats (CSV, SQL DDL, JSON), converts them into a canonical internal representation, extracts structural features, compares them against database capabilities, and produces ranked compatibility scores with explanations.

**Current status:** MVP CLI prototype with multi-format parsing and basic scoring engine.

## Features 

- Supports schema input in **CSV**, **SQL DDL**, and  **JSON** formats
- Parses table/column definitions, data types, constraints (PK, FK, NOT NULL, UNIQUE), and relationships
- Normalizes data types and infers missing constraint information
- Compares schema against a database capability knowledge base (`db_features.json`)
- Computes compatibility scores based on:
  - Data type support
  - Constraint support
  - Special feature usage (JSON, arrays, etc.)
- Outputs parsed schema and scoring results in JSON format
- Simple CLI interface with flexible arguments

## Project Structure
```
├── core/
│   ├── analyzer.py          # Feature extraction from parsed schema
│   └── scorer.py            # Compatibility scoring & ranking logic
├── data/
│   └── db_features.json     # Knowledge base of DBMS capabilities
├── parser/
│   └── schema_parser.py     # Multi-format schema parsing (CSV, SQL, JSON)
├── main.py                  # CLI entry point
├── sample_schema.csv        # Example input: CSV format
├── sample.sql               # Example input: SQL DDL format
├── README.md
├── LICENSE
└── .gitignore
```
