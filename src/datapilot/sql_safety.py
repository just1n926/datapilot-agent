from __future__ import annotations

import re


class UnsafeQueryError(ValueError):
    """Raised when a query can mutate state or access external resources."""


FORBIDDEN_KEYWORDS = {
    "alter",
    "attach",
    "call",
    "copy",
    "create",
    "delete",
    "detach",
    "drop",
    "export",
    "import",
    "insert",
    "install",
    "load",
    "merge",
    "pragma",
    "set",
    "truncate",
    "update",
}

FORBIDDEN_FUNCTIONS = {
    "glob",
    "parquet_scan",
    "postgres_scan",
    "read_blob",
    "read_csv",
    "read_csv_auto",
    "read_json",
    "read_json_auto",
    "read_parquet",
    "read_text",
    "read_xlsx",
    "sqlite_scan",
}


def validate_readonly_sql(sql: str, known_tables: set[str]) -> str:
    query = sql.strip()
    if query.endswith(";"):
        query = query[:-1].rstrip()
    if not query or len(query) > 8_000:
        raise UnsafeQueryError("query must contain 1-8000 characters")
    if "\x00" in query or "--" in query or "/*" in query or "*/" in query:
        raise UnsafeQueryError("SQL comments are not allowed")
    if ";" in query:
        raise UnsafeQueryError("multiple SQL statements are not allowed")

    lowered = query.lower()
    first_word = re.match(r"\s*([a-z_]+)", lowered)
    if not first_word or first_word.group(1) not in {"select", "with"}:
        raise UnsafeQueryError("only SELECT or WITH queries are allowed")

    tokens = set(re.findall(r"\b[a-z_][a-z0-9_]*\b", lowered))
    forbidden = sorted(tokens & (FORBIDDEN_KEYWORDS | FORBIDDEN_FUNCTIONS))
    if forbidden:
        raise UnsafeQueryError(f"forbidden SQL operation: {forbidden[0]}")
    if not any(re.search(rf"\b{re.escape(table.lower())}\b", lowered) for table in known_tables):
        raise UnsafeQueryError("query must reference a table from the selected dataset")
    return query

