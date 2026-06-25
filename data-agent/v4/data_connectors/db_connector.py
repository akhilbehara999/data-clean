# -*- coding: utf-8 -*-
"""
Feature 3B — Database connector (Postgres / MySQL).

Usage:
    python main.py --connect db --config db_config.json

db_config.json schema:
{
    "type": "postgres",   // or "mysql"
    "host": "...",
    "port": 5432,
    "database": "...",
    "user": "...",
    "password": "...",
    "table": "...",
    "query": "SELECT * FROM ... LIMIT 10000"
}

READ-ONLY. Refuses non-SELECT queries.
"""

from __future__ import annotations

import os
import json
import re
import hashlib
import datetime
from typing import Optional

import pandas as pd

CACHE_DIR = os.path.join("output", ".cache")

# Disallowed DML / DDL keywords (first real word of query)
_WRITE_KEYWORDS = {"insert", "update", "delete", "drop", "truncate",
                   "create", "alter", "replace", "merge", "call", "exec"}

_LARGE_ROW_WARN = 100_000  # warn if estimated rows > this


def _detect_no_limit(query: str) -> bool:
    """Heuristic: return True if query has no LIMIT clause."""
    return not bool(re.search(r"\bLIMIT\b", query, re.IGNORECASE))


def _first_keyword(query: str) -> str:
    tokens = query.strip().lower().split()
    return tokens[0] if tokens else ""


def _cache_path(config_hash: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"db_{config_hash}.pkl")


def load_db_config(config_path: str) -> Optional[dict]:
    if not os.path.exists(config_path):
        print(f"  ⚠ DB config file not found: {config_path}")
        _print_setup_instructions()
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("  ⚠ Failed to parse the database configuration file. Please check that it's a valid JSON file.")
        return None


def connect_db(config_path: str = "db_config.json") -> Optional[pd.DataFrame]:
    """
    Connect to a database, run the configured query, return DataFrame.
    Read-only — refuses any non-SELECT query.
    """
    cfg = load_db_config(config_path)
    if cfg is None:
        return None

    query = cfg.get("query", "").strip()
    if not query:
        table = cfg.get("table", "")
        if table:
            query = f"SELECT * FROM {table} LIMIT 10000"
        else:
            print("  ⚠ No 'query' or 'table' field in db_config.json.")
            return None

    # Safety: refuse write queries
    first_kw = _first_keyword(query)
    if first_kw in _WRITE_KEYWORDS:
        print(f"  ⚠ Refused: non-SELECT query detected ('{first_kw.upper()}').")
        print("    DataSanitizer is read-only. Only SELECT queries are allowed.")
        print("    Please update db_config.json with a SELECT query.")
        return None

    # Warn if no LIMIT
    if _detect_no_limit(query):
        print("  ⚠ This query has no LIMIT clause. It may return a very large number of rows.")
        answer = input("    Add 'LIMIT 10000' automatically? (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            query = query.rstrip(";") + " LIMIT 10000"
        else:
            print("    Proceeding without LIMIT — this may be slow or use excessive memory.")

    db_type = cfg.get("type", "postgres").lower()

    # Hash config for cache key
    config_hash = hashlib.md5(
        json.dumps({k: cfg[k] for k in cfg if k != "password"}, sort_keys=True).encode()
    ).hexdigest()[:8]
    cache = _cache_path(config_hash)

    try:
        df = _execute_query(db_type, cfg, query)
        df.to_pickle(cache)
        print(f"  [DB] Loaded {len(df):,} rows × {len(df.columns)} cols from database.")
        return df
    except ImportError as e:
        drv = "psycopg2" if db_type == "postgres" else "pymysql"
        print(f"  ⚠ DB driver not installed. Run: pip install {drv}")
        print("    Detail: Missing database driver dependency.")
        return None
    except Exception as e:
        print("  ⚠ Database connection failed. Please check your configuration and connection.")
        _print_setup_instructions()
        return None


def _execute_query(db_type: str, cfg: dict, query: str) -> pd.DataFrame:
    if db_type in ("postgres", "postgresql"):
        import psycopg2  # type: ignore
        conn = psycopg2.connect(
            host=cfg.get("host", "localhost"),
            port=cfg.get("port", 5432),
            database=cfg.get("database", ""),
            user=cfg.get("user", ""),
            password=cfg.get("password", ""),
        )
    elif db_type == "mysql":
        import pymysql  # type: ignore
        conn = pymysql.connect(
            host=cfg.get("host", "localhost"),
            port=cfg.get("port", 3306),
            database=cfg.get("database", ""),
            user=cfg.get("user", ""),
            password=cfg.get("password", ""),
        )
    else:
        raise ValueError(f"Unsupported database type: '{db_type}'. Use 'postgres' or 'mysql'.")

    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df


def _print_setup_instructions() -> None:
    print()
    print("  DB connection setup — create a db_config.json file:")
    print('  {')
    print('    "type": "postgres",')
    print('    "host": "localhost",')
    print('    "port": 5432,')
    print('    "database": "mydb",')
    print('    "user": "myuser",')
    print('    "password": "mypass",')
    print('    "query": "SELECT * FROM mytable LIMIT 10000"')
    print('  }')
    print("  Required packages: pip install psycopg2-binary  (Postgres)")
    print("                     pip install pymysql           (MySQL)")
    print()
    print("  For now, you can upload a CSV/Excel file directly instead.")
    print()
