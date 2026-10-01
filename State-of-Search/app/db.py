from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"


def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:state-of-search-demo@db:5432/state_of_search",
    )


def connect(*, dict_rows: bool = True):
    kwargs = {"row_factory": dict_row} if dict_rows else {}
    return psycopg.connect(database_url(), **kwargs)


def run_sql_file(conn: psycopg.Connection, name: str) -> None:
    sql = (SQL_DIR / name).read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

