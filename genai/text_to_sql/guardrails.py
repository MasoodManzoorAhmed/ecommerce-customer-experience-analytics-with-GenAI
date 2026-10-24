"""Safety checks on LLM-written SQL before it touches the database.

1. Exactly one statement, and it must be a query (SELECT / WITH ... SELECT / UNION).
2. Only tables from the allowed list (the star schema); CTE names are fine.
3. A LIMIT is added when the query has none, so a bad query can't return millions of rows.
The query then runs on a READ-ONLY connection with file access switched off and a timeout
(see run_safely), so even a query that slipped through could not change data or read files.
"""

from __future__ import annotations

import re
import threading

import duckdb
import sqlglot
from sqlglot import exp

from genai.text_to_sql.eval_set import ALLOWED_TABLES, run_query
from src.db import DB_PATH

DEFAULT_LIMIT = 1000
TIMEOUT_S = 15


class GuardrailError(ValueError):
    """The SQL was rejected before execution."""


def extract_sql(text: str) -> str:
    """Pull the SQL out of a model reply (handles ```sql fences and leading chatter)."""
    fenced = re.findall(r"```(?:sql|duckdb)?\s*(.*?)```", text, flags=re.S | re.I)
    sql = fenced[0] if fenced else text
    match = re.search(r"\b(WITH|SELECT)\b", sql, flags=re.I)
    if match:
        sql = sql[match.start() :]
    return sql.strip().rstrip(";").strip()


def check_sql(
    sql: str, allowed: frozenset[str] = ALLOWED_TABLES, limit: int = DEFAULT_LIMIT
) -> str:
    """Validate the query and return it (with a LIMIT added if missing). Raises GuardrailError."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as err:
        raise GuardrailError(f"could not parse SQL: {str(err).splitlines()[0]}") from err
    if len(statements) != 1:
        raise GuardrailError(f"expected one statement, got {len(statements)}")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise GuardrailError(f"only SELECT queries are allowed, got {tree.key.upper()}")
    for node in tree.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter)):
            raise GuardrailError(f"{node.key.upper()} is not allowed")
    table_nodes = list(tree.find_all(exp.Table))
    if any(not t.name or isinstance(t.this, exp.Func) for t in table_nodes):
        raise GuardrailError("table functions (read_csv, read_text, glob ...) are not allowed")
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    tables = {t.name for t in table_nodes} - ctes
    outside = sorted(tables - allowed)
    if outside:
        raise GuardrailError(f"tables not allowed: {', '.join(outside)}")
    if not tree.args.get("limit"):
        tree = tree.limit(limit)
    return tree.sql(dialect="duckdb")


def run_safely(sql: str, timeout_s: int = TIMEOUT_S) -> dict:
    """Execute already-checked SQL on a read-only connection with file access switched off
    (enable_external_access = false: no read_csv / read_text on local files, even if a query
    slipped past check_sql), and interrupt it after the timeout."""
    config = {"enable_external_access": False}
    with duckdb.connect(str(DB_PATH), read_only=True, config=config) as con:
        timer = threading.Timer(timeout_s, con.interrupt)
        timer.start()
        try:
            return run_query(con, sql)
        finally:
            timer.cancel()
