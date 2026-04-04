import os
import psycopg2
import psycopg2.extras
import sqlparse

from decimal import Decimal
from datetime import date, datetime
from typing import Dict, Any, List


# -----------------------------
# SQL SAFETY
# -----------------------------

FORBIDDEN_KEYWORDS = {
    "INSERT", "DELETE",
    "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE"
}


def _is_safe_select(sql: str) -> bool:
    """
    Allow exactly ONE SELECT statement.
    """
    parsed = sqlparse.parse(sql)

    if len(parsed) != 1:
        return False

    statement = parsed[0]

    if statement.get_type() != "SELECT":
        return False

    tokens = {token.value.upper() for token in statement.tokens if token.value}
    return not tokens.intersection(FORBIDDEN_KEYWORDS)


def _normalize_sql(sql: str) -> str:
    """
    Strip trailing semicolons and whitespace.
    """
    return sql.strip().rstrip(";").strip()


# -----------------------------
# JSON SAFETY
# -----------------------------

def _json_safe(value):
    """
    Convert Postgres-native types into JSON-safe values.
    """
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


# -----------------------------
# MAIN TOOL
# -----------------------------

def query_postgres(
    query: str,
    max_rows: int = 1000
) -> Dict[str, Any]:
    """
    Execute a read-only SQL SELECT query against Postgres.

    Parameters:
    - query: SQL SELECT statement (no semicolon required)
    - max_rows: hard safety cap on returned rows

    Returns:
    - row_count
    - rows (JSON-serializable)
    """

    if not query or not isinstance(query, str):
        return {"error": "Query must be a non-empty SQL string."}
    print(">>>>>>>>>>query:", query)
    sql = _normalize_sql(query)

    if not _is_safe_select(sql):
        return {"error": "Only a single SELECT statement is allowed."}

    try:
        conn = psycopg2.connect(
            host=os.environ["PG_HOST"],
            port=os.environ["PG_PORT"],
            user=os.environ["PG_USER"],
            password=os.environ["PG_PASSWORD"],
            dbname=os.environ["PG_DB"],
        )

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchmany(max_rows)

        safe_rows = [
            {k: _json_safe(v) for k, v in row.items()}
            for row in rows
        ]

        return {
            "row_count": len(safe_rows),
            "rows": safe_rows
        }

    except Exception as e:
        return {
            "error": f"Database execution error: {str(e)}"
        }

    finally:
        try:
            conn.close()
        except Exception:
            pass
