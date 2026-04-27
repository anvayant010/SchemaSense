from __future__ import annotations
import re
from core.models import ParsedSchema, Table, Column, Index
from core.scorer import _parse_and_canonicalize_type


def detect_db_type(connection_string: str) -> str:
    cs = connection_string.strip().lower()
    if cs.startswith("postgresql://") or cs.startswith("postgres://"):
        return "postgresql"
    elif cs.startswith("mysql://") or cs.startswith("mysql+pymysql://"):
        return "mysql"
    elif cs.startswith("sqlite:///") or cs.startswith("sqlite://"):
        return "sqlite"
    else:
        raise ValueError(
            "Unsupported connection string. Supported formats:\n"
            "  postgresql://user:pass@host:5432/dbname\n"
            "  mysql://user:pass@host:3306/dbname\n"
            "  sqlite:///path/to/database.db"
        )


def sanitize_error(error: Exception) -> str:
    """Strip credentials from error messages before sending to client."""
    msg = str(error)
    msg = re.sub(r'[a-zA-Z0-9_]+:[^@\s]+@[^\s/]+', '***:***@***', msg)
    msg = re.sub(r'(postgresql|postgres|mysql|sqlite)://\S+', r'\1://***', msg)
    return msg


def _introspect_postgresql(connection_string: str) -> ParsedSchema:
    try:
        import psycopg2
    except ImportError:
        raise RuntimeError("psycopg2-binary not installed.")

    conn = None
    try:
        conn = psycopg2.connect(connection_string, connect_timeout=10)
        cur = conn.cursor()

        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        table_names = [row[0] for row in cur.fetchall()]

        tables = []
        for table_name in table_names:
            cur.execute("""
                SELECT
                    c.column_name, c.data_type,
                    c.character_maximum_length,
                    c.numeric_precision, c.numeric_scale,
                    c.is_nullable, c.column_default,
                    CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_name = %s AND tc.table_schema = 'public'
                ) pk ON c.column_name = pk.column_name
                WHERE c.table_name = %s AND c.table_schema = 'public'
                ORDER BY c.ordinal_position
            """, (table_name, table_name))
            col_rows = cur.fetchall()

            cur.execute("""
                SELECT kcu.column_name, ccu.table_name, ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = %s AND tc.table_schema = 'public'
            """, (table_name,))
            fk_map = {r[0]: {"table": r[1], "column": r[2]} for r in cur.fetchall()}

            columns = []
            for col in col_rows:
                col_name, data_type, max_len, num_prec, num_scale, nullable, default, is_pk = col
                raw_type = data_type.upper()
                if max_len:
                    raw_type = f"{data_type}({max_len})"
                elif num_prec and num_scale:
                    raw_type = f"{data_type}({num_prec},{num_scale})"
                canon_type, length, precision, scale = _parse_and_canonicalize_type(raw_type)
                columns.append(Column(
                    name=col_name, data_type=canon_type, raw_type=raw_type,
                    length=length, precision=precision, scale=scale,
                    nullable=(nullable == 'YES'), is_primary_key=bool(is_pk),
                    is_foreign_key=(col_name in fk_map),
                    references=fk_map.get(col_name),
                    default=str(default) if default else None,
                ))
            tables.append(Table(name=table_name, columns=columns))

        cur.execute("""
            SELECT i.relname, t.relname, array_agg(a.attname), ix.indisunique
            FROM pg_index ix
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            JOIN pg_namespace ns ON ns.oid = t.relnamespace
            WHERE ns.nspname = 'public' AND NOT ix.indisprimary
            GROUP BY i.relname, t.relname, ix.indisunique
        """)
        indexes = [Index(name=r[0], table=r[1], columns=list(r[2]), unique=r[3]) for r in cur.fetchall()]

        return ParsedSchema(tables=tables, source_format="connection",
                           source_file="postgresql://***", indexes=indexes)
    except Exception as e:
        raise RuntimeError(f"PostgreSQL connection failed: {sanitize_error(e)}")
    finally:
        if conn:
            conn.close()


def _introspect_mysql(connection_string: str) -> ParsedSchema:
    try:
        import pymysql
        from urllib.parse import urlparse
    except ImportError:
        raise RuntimeError("pymysql not installed.")

    conn = None
    try:
        parsed = urlparse(connection_string.replace("mysql://", "http://"))
        host = parsed.hostname
        port = parsed.port or 3306
        user = parsed.username
        password = parsed.password
        database = parsed.path.lstrip("/")

        conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor
        )
        cur = conn.cursor()

        cur.execute("""
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """, (database,))
        table_names = [row["TABLE_NAME"] for row in cur.fetchall()]

        tables = []
        for table_name in table_names:
            cur.execute("""
                SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH,
                       NUMERIC_PRECISION, NUMERIC_SCALE, IS_NULLABLE,
                       COLUMN_DEFAULT, COLUMN_KEY
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (database, table_name))
            col_rows = cur.fetchall()

            cur.execute("""
                SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                  AND REFERENCED_TABLE_NAME IS NOT NULL
            """, (database, table_name))
            fk_map = {r["COLUMN_NAME"]: {"table": r["REFERENCED_TABLE_NAME"],
                      "column": r["REFERENCED_COLUMN_NAME"]} for r in cur.fetchall()}

            columns = []
            for col in col_rows:
                raw_type = col["DATA_TYPE"].upper()
                if col["CHARACTER_MAXIMUM_LENGTH"]:
                    raw_type = f"{col['DATA_TYPE']}({col['CHARACTER_MAXIMUM_LENGTH']})"
                elif col["NUMERIC_PRECISION"] and col["NUMERIC_SCALE"]:
                    raw_type = f"{col['DATA_TYPE']}({col['NUMERIC_PRECISION']},{col['NUMERIC_SCALE']})"
                canon_type, length, precision, scale = _parse_and_canonicalize_type(raw_type)
                columns.append(Column(
                    name=col["COLUMN_NAME"], data_type=canon_type, raw_type=raw_type,
                    length=length, precision=precision, scale=scale,
                    nullable=(col["IS_NULLABLE"] == "YES"),
                    is_primary_key=(col["COLUMN_KEY"] == "PRI"),
                    is_foreign_key=(col["COLUMN_NAME"] in fk_map),
                    references=fk_map.get(col["COLUMN_NAME"]),
                    default=str(col["COLUMN_DEFAULT"]) if col["COLUMN_DEFAULT"] else None,
                ))
            tables.append(Table(name=table_name, columns=columns))

        return ParsedSchema(tables=tables, source_format="connection",
                           source_file="mysql://***")
    except Exception as e:
        raise RuntimeError(f"MySQL connection failed: {sanitize_error(e)}")
    finally:
        if conn:
            conn.close()


def _introspect_sqlite(connection_string: str) -> ParsedSchema:
    import sqlite3
    try:
        db_path = connection_string.replace("sqlite:///", "").replace("sqlite://", "")
        conn = sqlite3.connect(db_path, timeout=10)
        cur = conn.cursor()

        cur.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        table_names = [row[0] for row in cur.fetchall()]

        tables = []
        for table_name in table_names:
            cur.execute(f"PRAGMA table_info('{table_name}')")
            col_rows = cur.fetchall()
            cur.execute(f"PRAGMA foreign_key_list('{table_name}')")
            fk_map = {r[3]: {"table": r[2], "column": r[4]} for r in cur.fetchall()}

            columns = []
            for col in col_rows:
                _, col_name, col_type, not_null, default, is_pk = col
                raw_type = (col_type or "TEXT").upper()
                canon_type, length, precision, scale = _parse_and_canonicalize_type(raw_type)
                columns.append(Column(
                    name=col_name, data_type=canon_type, raw_type=raw_type,
                    length=length, precision=precision, scale=scale,
                    nullable=(not bool(not_null)), is_primary_key=bool(is_pk),
                    is_foreign_key=(col_name in fk_map),
                    references=fk_map.get(col_name),
                    default=str(default) if default else None,
                ))
            tables.append(Table(name=table_name, columns=columns))

        cur.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        indexes = []
        for idx_name, tbl_name in cur.fetchall():
            cur.execute(f"PRAGMA index_info('{idx_name}')")
            cols = [r[2] for r in cur.fetchall()]
            indexes.append(Index(name=idx_name, table=tbl_name, columns=cols, unique=False))

        conn.close()
        return ParsedSchema(tables=tables, source_format="connection",
                           source_file="sqlite://***", indexes=indexes)
    except Exception as e:
        raise RuntimeError(f"SQLite connection failed: {sanitize_error(e)}")


def introspect_from_connection(connection_string: str) -> ParsedSchema:
    """
    Main entry point. Never logs or stores the connection string.
    Connects, introspects, disconnects immediately.
    """
    if not connection_string or not connection_string.strip():
        raise ValueError("Connection string cannot be empty")

    db_type = detect_db_type(connection_string.strip())

    if db_type == "postgresql":
        return _introspect_postgresql(connection_string.strip())
    elif db_type == "mysql":
        return _introspect_mysql(connection_string.strip())
    elif db_type == "sqlite":
        return _introspect_sqlite(connection_string.strip())