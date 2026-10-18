"""Data-quality audit: run sql/04_data_quality_checks.sql and profile missing values."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.db import load_named_sql

CHECKS_FILE = "04_data_quality_checks.sql"
AUDIT_COLUMNS = ["check", "table", "issue", "affected", "base", "pct", "decision", "action"]


def run_audit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Run every check and return one row per issue with its size, decision and action."""
    rows = []
    for check in load_named_sql(CHECKS_FILE):
        missing = {"table", "issue", "decision", "action"} - check.meta.keys()
        if missing:
            raise ValueError(f"check {check.name} is missing metadata: {sorted(missing)}")
        affected, base = con.execute(check.sql).fetchone()
        rows.append(
            {
                "check": check.name,
                **check.meta,
                "affected": int(affected),
                "base": int(base),
                "pct": round(100.0 * affected / base, 2) if base else 0.0,
            }
        )
    return pd.DataFrame(rows)[AUDIT_COLUMNS]


def missing_profile(con: duckdb.DuckDBPyConnection, schema: str = "raw") -> pd.DataFrame:
    """Count NULLs per column for every table in a schema (only columns with NULLs)."""
    cols = con.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = ? ORDER BY table_name, ordinal_position",
        [schema],
    ).fetchall()
    rows = []
    for table, column in cols:
        nulls, total = con.execute(
            f'SELECT COUNT(*) FILTER (WHERE "{column}" IS NULL), COUNT(*) FROM {schema}.{table}'
        ).fetchone()
        if nulls:
            rows.append(
                {
                    "table": table,
                    "column": column,
                    "nulls": nulls,
                    "rows": total,
                    "pct": round(100.0 * nulls / total, 2),
                }
            )
    return pd.DataFrame(rows).sort_values("pct", ascending=False, ignore_index=True)
