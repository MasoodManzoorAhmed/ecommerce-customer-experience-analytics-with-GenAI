"""Database access and named-SQL parsing shared by scripts, notebooks and the app."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "olist.duckdb"
SQL_DIR = ROOT / "sql"

NAME_MARKER = re.compile(r"^-- name:\s*(\S+)\s*$", re.MULTILINE)
META_LINE = re.compile(r"^-- (table|issue|decision|action):\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class NamedQuery:
    """One "-- name:" block from a SQL file, with any metadata comment lines."""

    name: str
    sql: str
    meta: dict[str, str] = field(default_factory=dict)


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Open the project database (read-only by default, so analysis cannot change data)."""
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def parse_named_sql(sql_text: str) -> list[NamedQuery]:
    """Split SQL text on "-- name: x" markers and collect "-- key: value" metadata."""
    parts = NAME_MARKER.split(sql_text)
    # parts = [header, name1, body1, name2, body2, ...]
    queries = []
    for name, body in zip(parts[1::2], parts[2::2], strict=True):
        meta = {key: value for key, value in META_LINE.findall(body)}
        queries.append(NamedQuery(name=name, sql=body.strip(), meta=meta))
    return queries


def load_named_sql(filename: str) -> list[NamedQuery]:
    """Parse a file from the sql/ folder."""
    return parse_named_sql((SQL_DIR / filename).read_text(encoding="utf-8"))
