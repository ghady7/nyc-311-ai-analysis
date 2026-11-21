"""
SQL AST & Regex Security Guardrail Module
Validates, sanitizes, and enforces read-only invariants on AI-generated SQL queries
before execution against the Supabase PostgreSQL database.
"""

import re
from typing import Tuple, Optional, Set

# Strict list of prohibited DDL, DML, administrative keywords, and dangerous routines
FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "COPY", "CREATE", "REPLACE", "EXEC",
    "EXECUTE", "CALL", "VACUUM", "COMMENT", "LOCK", "SET",
    "DO", "BEGIN", "COMMIT", "ROLLBACK", "MERGE",
    "PG_SLEEP", "PG_TERMINATE_BACKEND", "PG_CANCEL_BACKEND",
    "PG_READ_FILE", "PG_LS_DIR", "DBLINK"
}

# Explicit whitelist of authorized NYC 311 database tables in public schema
ALLOWED_TABLES = {
    "fact_complaints",
    "dim_agency",
    "dim_complaint_type",
    "dim_location",
    "dim_calendar",
    "quarantine_complaints"
}

# Forbidden system catalog tables and security-sensitive namespaces
FORBIDDEN_TABLES = {
    "pg_shadow", "pg_authid", "pg_user", "pg_roles", "pg_database",
    "pg_tablespace", "pg_stat_activity", "pg_proc", "pg_settings",
    "information_schema.user_mappings"
}

# Forbidden schema prefixes and system namespaces
FORBIDDEN_SCHEMAS = {
    "auth", "vault", "storage", "realtime", "supabase_migrations",
    "extensions", "pg_catalog", "information_schema"
}

MAX_ROW_LIMIT = 100


class SecurityViolationError(Exception):
    """Raised when a SQL query violates read-only AST guardrail rules."""
    pass


def strip_sql_comments(sql: str) -> str:
    """Remove single-line (--) and multi-line (/* */) SQL comments while strictly preserving string literals."""
    result = []
    i = 0
    n = len(sql)
    in_single_quote = False
    in_double_quote = False

    while i < n:
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < n else ""

        if char == "'" and not in_double_quote:
            # Handle escaped quote ''
            if in_single_quote and next_char == "'":
                result.append("''")
                i += 2
                continue
            in_single_quote = not in_single_quote
            result.append(char)
            i += 1
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            result.append(char)
            i += 1
        elif not in_single_quote and not in_double_quote:
            # Check for multi-line comment /* ... */
            if char == "/" and next_char == "*":
                i += 2
                while i < n - 1 and not (sql[i] == "*" and sql[i + 1] == "/"):
                    i += 1
                i += 2  # skip closing */
                result.append(" ")
            # Check for single-line comment --
            elif char == "-" and next_char == "-":
                i += 2
                while i < n and sql[i] != "\n":
                    i += 1
                if i < n and sql[i] == "\n":
                    result.append("\n")
                    i += 1
            else:
                result.append(char)
                i += 1
        else:
            result.append(char)
            i += 1

    return "".join(result).strip()


def validate_single_statement(sql: str) -> str:
    """
    Ensure the query contains exactly one SQL statement.
    Rejects chained queries (semicolon abuse / SQL injection).
    """
    clean = sql.strip()
    if clean.endswith(";"):
        clean = clean[:-1].strip()

    # Check for unquoted semicolons
    in_single_quote = False
    in_double_quote = False
    for char in clean:
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == ";" and not in_single_quote and not in_double_quote:
            raise SecurityViolationError("Multiple SQL statements detected (semicolon chaining is prohibited).")

    return clean


def enforce_read_only_ast(sql: str) -> str:
    """
    Parse SQL tokens and verify that statement is strictly a SELECT query.
    Blocks all mutation, administrative, and data exfiltration patterns.
    """
    stripped = strip_sql_comments(sql)
    if not stripped:
        raise SecurityViolationError("Empty SQL query provided.")

    single_statement = validate_single_statement(stripped)

    # Tokenize words outside quoted literals
    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", single_statement)
    if not tokens:
        raise SecurityViolationError("No valid SQL tokens found.")

    first_keyword = tokens[0].upper()
    if first_keyword not in ("SELECT", "WITH"):
        raise SecurityViolationError(f"Prohibited statement type '{first_keyword}'. Only SELECT and WITH queries are authorized.")

    # Block recursive CTEs (Denial of Service risk)
    if first_keyword == "WITH" and re.search(r"\bWITH\s+RECURSIVE\b", single_statement, re.IGNORECASE):
        raise SecurityViolationError("Recursive CTEs (WITH RECURSIVE) are prohibited for safety.")

    # Check for forbidden keywords anywhere in token stream
    upper_tokens = [t.upper() for t in tokens]
    for kw in upper_tokens:
        if kw in FORBIDDEN_KEYWORDS:
            raise SecurityViolationError(f"Security violation: Prohibited keyword '{kw}' detected.")

    # Check for forbidden schema references (e.g. auth.users, vault.secrets)
    for schema in FORBIDDEN_SCHEMAS:
        if re.search(r"\b" + re.escape(schema) + r"\.", single_statement, re.IGNORECASE):
            raise SecurityViolationError(f"Access to internal/administrative schema '{schema}' is strictly prohibited.")

    # Check for forbidden system catalogs
    lower_sql = single_statement.lower()
    for sys_tbl in FORBIDDEN_TABLES:
        if re.search(r"\b" + re.escape(sys_tbl) + r"\b", lower_sql):
            raise SecurityViolationError(f"Access to sensitive system catalog '{sys_tbl}' is strictly blocked.")

    # Check for 'INTO' clause (prevent SELECT INTO table creation)
    if re.search(r"\bINTO\b", single_statement, re.IGNORECASE):
        # Ensure it's not inside a string literal
        if not re.search(r"'.*?\bINTO\b.*?'", single_statement, re.IGNORECASE):
            raise SecurityViolationError("SELECT INTO statements are prohibited.")

    # Enforce strict table whitelist for FROM and JOIN clauses
    cte_names = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", single_statement, re.IGNORECASE))
    from_join_tables = re.findall(r"\b(?:FROM|JOIN)\s+(?:public\.)?([A-Za-z_][A-Za-z0-9_]*)", single_statement, re.IGNORECASE)

    for tbl in from_join_tables:
        tbl_lower = tbl.lower()
        if tbl_lower not in ALLOWED_TABLES and tbl_lower not in {c.lower() for c in cte_names}:
            raise SecurityViolationError(f"Access to unauthorized table '{tbl}'. Only NYC 311 analytics tables are permitted.")

    return single_statement


def enforce_limit_clause(sql: str, max_limit: int = MAX_ROW_LIMIT) -> str:
    """
    Ensure the query has an enforced LIMIT clause capped at max_limit.
    Appends LIMIT max_limit if absent, or caps existing limit if it exceeds max_limit.
    """
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)

    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit > max_limit or current_limit <= 0:
            sql = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {max_limit}", sql, flags=re.IGNORECASE)
    else:
        sql = f"{sql} LIMIT {max_limit}"

    return sql


def sanitize_and_guard_query(raw_sql: str, max_limit: int = MAX_ROW_LIMIT) -> str:
    """
    Master pipeline: Strip markdown code blocks, enforce read-only AST,
    and enforce row cap. Returns safe, production-ready SQL.
    """
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", raw_sql, re.IGNORECASE)
    if match:
        clean = match.group(1).strip()
    else:
        clean = re.sub(r"^```(?:sql)?\s*", "", raw_sql.strip(), flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean.strip())

    guarded = enforce_read_only_ast(clean)
    final_sql = enforce_limit_clause(guarded, max_limit)

    return final_sql
